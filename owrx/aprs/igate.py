from owrx.config import Config
from owrx.aprs import encoding
from owrx.version import openwebrx_version
import logging
import queue
import socket
import threading

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 14580
_SOFTWARE_ID = "OpenWebRX+ " + openwebrx_version;


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


class AprsIsIgate(object):
    creationLock = threading.Lock()
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        with AprsIsIgate.creationLock:
            if AprsIsIgate.sharedInstance is None:
                AprsIsIgate.sharedInstance = AprsIsIgate()
            return AprsIsIgate.sharedInstance

    def __init__(self):
        self._queue = queue.Queue()
        self._connLock = threading.Lock()
        self._socket = None
        self._worker = threading.Thread(target=self._run, name="AprsIsIgate", daemon=True)
        self._worker.start()
        self._configSub = Config.get().filter(
            "aprs_igate_enabled",
            "aprs_igate_server",
            "aprs_callsign",
            "aprs_igate_password",
        ).wire(self._onConfigChanged)

    def _onConfigChanged(self, *args):
        self._disconnect()

    def forward_ax25(self, data):
        pm = Config.get()
        if not pm["aprs_igate_enabled"]:
            return

        callsign = pm["aprs_callsign"].strip()
        if not callsign or callsign == "N0CALL":
            logger.debug("APRS-IS forwarding disabled: configure aprs_callsign")
            return

        password = pm["aprs_igate_password"]
        if password is None or str(password).strip() == "":
            logger.debug("APRS-IS forwarding disabled: configure aprs_igate_password")
            return

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
        packet = (line + "\r\n").encode("ascii")
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
