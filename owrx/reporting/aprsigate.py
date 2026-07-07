from owrx.reporting.reporter import FilteredReporter
from owrx.version import openwebrx_version
from owrx.config import Config

import logging
import queue
import socket
import threading
import re

logger = logging.getLogger(__name__)

PoisonPill = object()


class AprsIgate(FilteredReporter):
    DEFAULT_PORT = 14580
    BEACON_INITIAL_DELAY = 30
    BEACON_INTERVAL = 1800
    FEET_PER_METER = 3.28084

    def __init__(self):
        self.connLock = threading.Lock()
        self.queue = queue.Queue(500)
        self.socket = None
        self.enabled = None
        self.rejected = False
        self.beaconThread = None
        self.beaconWait = threading.Event()
        # Run reporter thread
        self.thread = threading.Thread(target=self.run, name="AprsIsIgate", daemon=True)
        self.thread.start()
        # Subscribe to APRS iGate changes
        self.locationSub = Config.get().filter("receiver_gps").wire(self.onLocationChanged)
        self.configSub = Config.get().filter(
            "aprs_igate_enabled",
            "aprs_igate_legacy",
            "aprs_igate_server",
            "aprs_callsign",
            "aprs_igate_password",
            "aprs_igate_beacon"
        ).wire(self.onConfigChanged)
        # Initiate first config change, enabling beacon if needed
        self.onConfigChanged()

    # Only supporting APRS packets (not AIS)
    def getSupportedModes(self):
        return ["APRS"]

    # Stop all threads
    def stop(self):
        # Stop beacons
        self.enableBeacon(False)
        # Stop main thread
        if self.thread is not None:
            while not self.queue.empty():
                self.queue.get(timeout=1)
                self.queue.task_done()
            self.queue.put(PoisonPill)

    # Queue up received packet
    def spot(self, spot):
        if self.isEnabled():
            pm = Config.get()
            try:
                self.queue.put(self.buildTnc2Line(spot, pm["aprs_callsign"]))
            except Exception:
                logger.exception("Failed to build APRS-IS packet")

    # When location changes, issue a new beacon
    def onLocationChanged(self, *args):
        if self.beaconThread is not None:
            self.beaconWait.set()

    # When settings change, validate them and reconnect
    def onConfigChanged(self, *args):
        # Verify all the important settings
        pm = Config.get()
        if not pm["aprs_igate_enabled"] or pm["aprs_igate_legacy"] or not pm["aprs_igate_password"]:
            self.enabled = False
        elif not pm["aprs_callsign"] or pm["aprs_callsign"] == "N0CALL":
            self.enabled = False
        else:
            self.enabled = True
        # Start or stop beacons as necessary
        self.enableBeacon(self.isBeaconEnabled())
        # Close current connection to the server
        self.disconnect()

    # Enabled when settings are valid and APRS-IS has not rejected us
    def isEnabled(self):
        return self.enabled and not self.rejected

    def isBeaconEnabled(self):
        pm = Config.get()
        return self.isEnabled() and pm["aprs_igate_beacon"]

    # Build TNC2-compatible message
    def buildTnc2Line(self, data, callsign):
        src  = data.get("source", "")
        dst  = data.get("destination", "")
        dst  = dst if dst else "APRS"
        path = data.get("path", [])
        path = ",".join(path)
        info = data.get("data", "")
        return f"{src}>{dst},{path},qAO,{callsign}:{info}"

    # Build our IGate position, including symbol
    def buildPosition(self, lat, lon, symbol):
        direction = "N" if lat >= 0 else "S"
        lat = abs(lat)
        lat_s = "{:02d}{:05.2f}{}".format(int(lat), (lat - int(lat)) * 60, direction)

        direction = "E" if lon >= 0 else "W"
        lon = abs(lon)
        lon_s = "{:03d}{:05.2f}{}".format(int(lon), (lon - int(lon)) * 60, direction)
        lon_deg = lon_s[0:3]
        lon_min = lon_s[3:8]
        lon_hem = lon_s[8]

        if len(symbol) >= 2:
            table, symch = symbol[0], symbol[1]
        elif len(symbol) == 1:
            table, symch = symbol[0], symbol[0]
        else:
            table, symch = "/", "&"

        # 20 data bytes (indices 0-19): "!", lat[0:8], table[8], lon[9:17], symbol[18].
        # Primary table: "/" at index 8 also separates lat from lon.
        # Overlay (R&, M&, …): overlay replaces "/" at index 8; lon follows immediately.
        if table == "/":
            body = f"!{lat_s}/{lon_deg}{lon_min}{lon_hem}{symch}"
        else:
            body = f"!{lat_s}{table}{lon_deg}{lon_min}{lon_hem}{symch}"

        if len(body) != 20:
            raise ValueError("Invalid APRS position length %d: %r" % (len(body), body))
        return body

    # Build beacon message
    def buildBeaconLine(self, callsign):
        pm = Config.get()
        gps = pm["receiver_gps"]
        info = self.buildPosition(gps["lat"], gps["lon"], pm["aprs_igate_symbol"])

        if "aprs_igate_comment" in pm and pm["aprs_igate_comment"]:
            info += " " + pm["aprs_igate_comment"]

        if "aprs_igate_height" in pm and pm["aprs_igate_height"]:
            try:
                heightFt = round(float(pm["aprs_igate_height"]) * self.FEET_PER_METER)
                info += " HEIGHT=" + str(heightFt)
            except (TypeError, ValueError):
                logger.error("Cannot parse aprs_igate_height: %s", pm["aprs_igate_height"])

        if "aprs_igate_gain" in pm and pm["aprs_igate_gain"]:
            info += " GAIN=" + str(pm["aprs_igate_gain"])

        if "aprs_igate_dir" in pm and pm["aprs_igate_dir"]:
            info += " DIR=" + str(pm["aprs_igate_dir"])

        return f"{callsign}>APRS:{info}"

    # Start or stop beacon thread
    def enableBeacon(self, enable):
        if not enable and self.beaconThread is not None:
            # Stop current beacon thread
            thread = self.beaconThread
            self.beaconThread = None
            self.beaconWait.set()
            thread.join()
        elif enable and self.beaconThread is None:
            # Start a new beacon thread
            self.beaconThread = threading.Thread(target=self.beaconLoop, name="AprsIsBeacon", daemon=True)
            self.beaconThread.start()

    # Beacon thread periodically queueing beacon packets
    def beaconLoop(self):
        pm = Config.get()
        # Delay sending beacons
        self.beaconWait.wait(self.BEACON_INITIAL_DELAY)
        self.beaconWait.clear()
        # Periodically send beacons
        while self.beaconThread is not None:
            if self.isBeaconEnabled():
                try:
                    self.queue.put(self.buildBeaconLine(pm["aprs_callsign"]))
                except Exception:
                    logger.exception("APRS-IS beacon failed")
            self.beaconWait.wait(self.BEACON_INTERVAL)
            self.beaconWait.clear()
        # Done sending beacons
        self.beaconThread = None

    # Main thread sending queued packets to APRS-IS
    def run(self):
        while True:
            line = self.queue.get()
            if line is PoisonPill:
                break
            try:
                self.send(line)
            except Exception:
                logger.exception("APRS-IS forward failed")
        self.disconnect()
        self.thread = None

    # Send message to the APRS-IS server, connecting as needed
    def send(self, line):
        with self.connLock:
            if not self.connect() or self.rejected:
                return
            try:
                self.socket.sendall((line.rstrip() + "\r\n").encode("ascii"))
                logger.debug("Forwarded packet to APRS-IS: %s", line)
            except OSError:
                logger.warning("APRS-IS connection lost while sending")
                self.disconnect()

    # Disconnect from the APRS-IS server
    def disconnect(self):
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
        self.rejected = False
        self.socket = None

    # Connect and authenticate with the APRS-IS server
    def connect(self):
        if self.socket is not None:
            return True

        # Not rejected yet
        self.rejected = False

        pm = Config.get()
        try:
            host = pm["aprs_igate_server"]
            if not host:
                raise ValueError("APRS-IS server is not configured")
            elif ":" in host:
                host, port = host.rsplit(":", 1)
                port = int(port)
            else:
                port = self.DEFAULT_PORT
        except Exception:
            logger.exception("Invalid APRS-IS server configuration")
            return False

        callsign = pm["aprs_callsign"]
        password = pm["aprs_igate_password"]
        software = "OpenWebRX " + openwebrx_version
        login    = f"user {callsign} pass {password} vers {software}\r\n"

        try:
            sock = socket.create_connection((host, port), timeout = 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(login.encode("ascii"))
            sock.settimeout(5)
            try:
                resp = sock.recv(4096).decode("ascii", "replace")
                logger.info(f"Received APRS-IS server response 1/2: {resp}")
                resp = sock.recv(4096).decode("ascii", "replace")
                logger.info(f"Received APRS-IS server response 2/2: {resp}")
                self.rejected = f"# logresp {callsign} verified," not in resp
            except socket.timeout:
                pass
            sock.settimeout(None)
            self.socket = sock
            logger.info("%s by APRS-IS server %s:%d as %s",
                "Rejected" if self.rejected else "Accepted",
                host, port, callsign
            )
            return True
        except OSError:
            logger.warning("Could not connect to APRS-IS server %s:%d", host, port)
            self.disconnect()
            return False
