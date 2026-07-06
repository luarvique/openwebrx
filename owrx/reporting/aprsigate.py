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
        self.verified = False
        self.beaconThread = None
        self.beaconStop = threading.Event()
        # Run reporter thread
        self.thread = threading.Thread(target=self.run, name="AprsIsIgate", daemon=True)
        self.thread.start()
        # Subscribe to APRS iGate changes
        self.locationSub = Config.get().filter("receiver_gps").wire(self.onLocationChanged)
        self.configSub = Config.get().filter(
            "aprs_igate_enabled",
            "aprs_igate_server",
            "aprs_callsign",
            "aprs_igate_password",
            "aprs_igate_beacon"
        ).wire(self.onConfigChanged)
        # Initiate first config change, enabling beacon if needed
        self.onConfigChanged()

    def getSupportedModes(self):
        return ["APRS"]

    def stop(self):
        # Stop beacons
        self.enableBeacon(False)
        # Stop main thread
        if self.thread is not None:
            while not self.queue.empty():
                self.queue.get(timeout=1)
                self.queue.task_done()
            self.queue.put(PoisonPill)

    def spot(self, spot):
        callsign = self.getCallsignWhenEnabled()
        if callsign and spot["source"] != "AIS":
            try:
                self.queue.put(self.buildTnc2Line(spot, callsign))
            except Exception:
                logger.exception("Failed to build APRS-IS packet")

    def onLocationChanged(self, *args):
        if self.beaconThread is not None:
            self.beaconStop.set()

    def onConfigChanged(self, *args):
        # Start or stop beacons as necessary
        pm = Config.get()
        self.enableBeacon(pm["aprs_igate_enabled"] and pm["aprs_igate_beacon"])
        # Close current connection to the server
        self.disconnect()

    def getCallsignWhenEnabled(self):
        pm = Config.get()
        if not pm["aprs_igate_enabled"] or not pm["aprs_igate_password"]:
            return None
        callsign = pm["aprs_callsign"]
        if not callsign or callsign == "N0CALL":
            return None
        return callsign

    def buildTnc2Line(self, data, callsign):
        src  = data.get("source", "")
        dst  = data.get("destination", "")
        dst  = dst if dst else "APRS"
        path = data.get("path", [])
        path = ",".join(path)
        info = data.get("data", "")
        return f"{src}>{dst},{path},qAO,{callsign}:{info}"

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

    def enableBeacon(self, enable):
        # Stop current beacon thread
        if self.beaconThread is not None:
            thread = self.beaconThread
            self.beaconThread = None
            self.beaconStop.set()
            thread.join()
        # Start a new beacon thread
        if enable:
            self.beaconThread = threading.Thread(target=self.beaconLoop, name="AprsIsBeacon", daemon=True)
            self.beaconThread.start()

    def beaconLoop(self):
        # Delay sending beacons
        self.beaconStop.wait(self.BEACON_INITIAL_DELAY)
        # Periodically send beacons
        while self.beaconThread is not None:
            callsign = self.getCallsignWhenEnabled()
            if callsign:
                try:
                    self.queue.put(self.buildBeaconLine(callsign))
                except Exception:
                    logger.exception("APRS-IS beacon failed")
            self.beaconStop.wait(self.BEACON_INTERVAL)
        # Done sending beacons
        self.beaconThread = None
        self.beaconStop.clear()

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

    def send(self, line):
        with self.connLock:
            if not self.connect() or not self.verified:
                return
            try:
                self.socket.sendall((line.rstrip() + "\r\n").encode("ascii"))
                logger.debug("Forwarded packet to APRS-IS: %s", line)
            except OSError:
                logger.warning("APRS-IS connection lost while sending")
                self.disconnect()

    def disconnect(self):
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
        self.verified = False
        self.socket = None

    def connect(self):
        if self.socket is not None:
            return True

        # Not verified yet
        self.verified = False

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
                self.verified = f"# logresp {callsign} verified," in resp
            except socket.timeout:
                pass
            sock.settimeout(None)
            self.socket = sock
            logger.info("%s at APRS-IS server %s:%d as %s",
                "Verified" if self.verified else "UNVERIFIED",
                host, port, callsign
            )
            return True
        except OSError:
            logger.warning("Could not connect to APRS-IS server %s:%d", host, port)
            self.disconnect()
            return False
