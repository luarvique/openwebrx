from owrx.config import Config
from owrx.aprs import encoding
from owrx.version import openwebrx_version
import logging
import queue
import socket
import threading

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 14580
_SOFTWARE_ID = "OpenWebRX+ " + openwebrx_version
_BEACON_INITIAL_DELAY = 30
_BEACON_INTERVAL = 1800
FEET_PER_METER = 3.28084


def build_tnc2_line(data):
    source = data.get("source", "")
    destination = data.get("destination", "")
    path = data.get("path") or []
    info = data.get("data", b"")
    if isinstance(info, bytes):
        info = info.decode(encoding, "replace")

    path_parts = []
    if destination:
        path_parts.append(destination)
    path_parts.extend(path)
    path_str = ",".join(path_parts)
    return "{source}>{path}:{info}".format(source=source, path=path_str, info=info)


def add_igate_path(line, igate_callsign):
    if not igate_callsign:
        return line
    upper = line.upper()
    if ",QAO," in upper or ",QAR," in upper:
        return line

    colon = line.find(":")
    if colon < 0:
        return line

    return line[:colon] + ",qAO," + igate_callsign + line[colon:]


def parse_server(server):
    server = server.strip()
    if not server:
        raise ValueError("APRS-IS server is not configured")
    if ":" in server:
        host, port = server.rsplit(":", 1)
        return host, int(port)
    return server, _DEFAULT_PORT


def _format_lat(lat):
    direction = "N" if lat >= 0 else "S"
    lat = abs(lat)
    return "{:02d}{:05.2f}{}".format(int(lat), (lat - int(lat)) * 60, direction)


def _format_lon(lon):
    direction = "E" if lon >= 0 else "W"
    lon = abs(lon)
    return "{:03d}{:05.2f}{}".format(int(lon), (lon - int(lon)) * 60, direction)


def build_uncompressed_position(lat, lon, symbol):
    """
    Build a 19-byte APRS uncompressed position (matches AprsParser.parseUncompressedCoordinates).
    The two-character symbol places overlay/table at index 8 and the symbol at index 18.
    """
    lat_s = _format_lat(lat)
    lon_s = _format_lon(lon)
    lon_deg = lon_s[0:3]
    lon_min = lon_s[3:8]
    lon_hem = lon_s[8]

    if len(symbol) >= 2:
        table, symch = symbol[0], symbol[1]
    elif len(symbol) == 1:
        table, symch = symbol[0], symbol[0]
    else:
        table, symch = "/", "&"

    # 19 data bytes (indices 0-18): lat[0:8], table[8], lon[9:17], symbol[18].
    # Primary table: "/" at index 8 also separates lat from lon.
    # Overlay (R&, M&, …): overlay replaces "/" at index 8; lon follows immediately.
    if table == "/":
        body = "{lat}/{lon_deg}{lon_min}{lon_hem}{symch}".format(
            lat=lat_s, lon_deg=lon_deg, lon_min=lon_min, lon_hem=lon_hem, symch=symch
        )
    else:
        body = "{lat}{table}{lon_deg}{lon_min}{lon_hem}{symch}".format(
            lat=lat_s, table=table, lon_deg=lon_deg, lon_min=lon_min, lon_hem=lon_hem, symch=symch
        )
    if len(body) != 19:
        raise ValueError("invalid APRS position length %d: %r" % (len(body), body))
    return "!" + body


def _beacon_comment_parts(pm):
    parts = []
    if "aprs_igate_comment" in pm:
        comment = (pm["aprs_igate_comment"] or "").strip()
        if comment:
            parts.append(comment)
    if "aprs_igate_height" in pm:
        try:
            height_ft = round(float(pm["aprs_igate_height"]) * FEET_PER_METER)
            parts.append("HEIGHT=%d" % height_ft)
        except (TypeError, ValueError):
            logger.error("Cannot parse aprs_igate_height: %s", pm["aprs_igate_height"])
    if "aprs_igate_gain" in pm:
        gain = pm["aprs_igate_gain"]
        if gain is not None and str(gain).strip() != "":
            parts.append("GAIN=%s" % gain)
    if "aprs_igate_dir" in pm and pm["aprs_igate_dir"]:
        parts.append("DIR=%s" % pm["aprs_igate_dir"])
    return parts


def build_beacon_line():
    pm = Config.get()
    gps = pm["receiver_gps"]
    callsign = pm["aprs_callsign"].strip()
    symbol = pm["aprs_igate_symbol"]

    info = build_uncompressed_position(gps["lat"], gps["lon"], symbol)
    comment_parts = _beacon_comment_parts(pm)
    if comment_parts:
        info += " " + " ".join(comment_parts)

    return "{callsign}>APRS:{info}".format(callsign=callsign, info=info)


class AprsIsIgate(object):
    creationLock = threading.Lock()
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        with AprsIsIgate.creationLock:
            if AprsIsIgate.sharedInstance is None:
                AprsIsIgate.sharedInstance = AprsIsIgate()
            return AprsIsIgate.sharedInstance

    @staticmethod
    def ensureStarted():
        if Config.get()["aprs_igate_enabled"]:
            AprsIsIgate.getSharedInstance()

    def __init__(self):
        self._queue = queue.Queue()
        self._connLock = threading.Lock()
        self._socket = None
        self._beaconStop = threading.Event()
        self._beaconThread = None
        self._worker = threading.Thread(target=self._run, name="AprsIsIgate", daemon=True)
        self._worker.start()
        self._configSub = Config.get().filter(
            "aprs_igate_enabled",
            "aprs_igate_server",
            "aprs_callsign",
            "aprs_igate_password",
            "aprs_igate_beacon",
            "receiver_gps",
            "aprs_igate_symbol",
            "aprs_igate_comment",
            "aprs_igate_height",
            "aprs_igate_gain",
            "aprs_igate_dir",
        ).wire(self._onConfigChanged)
        self._syncBeacon()
        if self._canForward():
            threading.Thread(target=self._connectEarly, name="AprsIsConnect", daemon=True).start()

    def _connectEarly(self):
        with self._connLock:
            self._ensure_connected()

    def _onConfigChanged(self, *args):
        self._disconnect()
        self._syncBeacon()
        if self._canForward():
            threading.Thread(target=self._connectEarly, name="AprsIsConnect", daemon=True).start()

    def _syncBeacon(self):
        if self._beaconThread is not None:
            self._beaconStop.set()
            self._beaconThread.join()
            self._beaconStop.clear()
            self._beaconThread = None

        pm = Config.get()
        if pm["aprs_igate_enabled"] and pm["aprs_igate_beacon"]:
            self._beaconThread = threading.Thread(target=self._beaconLoop, name="AprsIsBeacon", daemon=True)
            self._beaconThread.start()

    def _beaconLoop(self):
        if self._beaconStop.wait(_BEACON_INITIAL_DELAY):
            return
        while not self._beaconStop.is_set():
            try:
                self._sendBeacon()
            except Exception:
                logger.exception("APRS-IS beacon failed")
            if self._beaconStop.wait(_BEACON_INTERVAL):
                return

    def _sendBeacon(self):
        if not self._canForward():
            return
        try:
            line = build_beacon_line()
        except Exception:
            logger.exception("failed to build APRS-IS beacon")
            return
        logger.info("sending APRS-IS beacon: %s", line)
        self._queue.put(line)

    def _canForward(self):
        pm = Config.get()
        if not pm["aprs_igate_enabled"]:
            return False
        callsign = pm["aprs_callsign"].strip()
        if not callsign or callsign == "N0CALL":
            return False
        password = pm["aprs_igate_password"]
        if password is None or str(password).strip() == "":
            return False
        return True

    def forward_ax25(self, data):
        if data.get("source") == "AIS":
            return
        if not self._canForward():
            return

        callsign = Config.get()["aprs_callsign"].strip()
        try:
            line = add_igate_path(build_tnc2_line(data), callsign)
        except Exception:
            logger.exception("failed to build APRS-IS packet")
            return

        self._queue.put(line)

    def _run(self):
        while True:
            line = self._queue.get()
            try:
                self._send(line)
            except Exception:
                logger.exception("APRS-IS forward failed")

    def _send(self, line):
        packet = (line.rstrip() + "\r\n").encode("ascii")
        with self._connLock:
            if not self._ensure_connected():
                return
            try:
                self._socket.sendall(packet)
                logger.debug("forwarded packet to APRS-IS: %s", line)
            except OSError:
                logger.warning("APRS-IS connection lost while sending")
                self._disconnect()

    def _ensure_connected(self):
        if self._socket is not None:
            return True

        pm = Config.get()
        try:
            host, port = parse_server(pm["aprs_igate_server"])
        except Exception:
            logger.exception("invalid APRS-IS server configuration")
            return False

        callsign = pm["aprs_callsign"].strip()
        password = str(pm["aprs_igate_password"]).strip()
        login = "user {callsign} pass {password} vers {software}\r\n".format(
            callsign=callsign,
            password=password,
            software=_SOFTWARE_ID,
        )

        try:
            sock = socket.create_connection((host, port), timeout=10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(login.encode("ascii"))
            sock.settimeout(2)
            try:
                sock.recv(4096)
            except socket.timeout:
                pass
            sock.settimeout(None)
            self._socket = sock
            logger.info("connected to APRS-IS server %s:%d as %s", host, port, callsign)
            return True
        except OSError:
            logger.warning("could not connect to APRS-IS server %s:%d", host, port)
            self._disconnect()
            return False

    def _disconnect(self):
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
