from owrx.reporting.reporter import FilteredReporter
from owrx.version import openwebrx_version
from owrx.config import Config
from owrx.aprs import encoding

import logging
import queue
import socket
import threading

logger = logging.getLogger(__name__)

PoisonPill = object()


class AprsReporter(FilteredReporter):
    DEFAULT_PORT = 14580

    def __init__(self):
        self.connLock = threading.Lock()
        self.queue = queue.Queue(500)
        self.socket = None
        # Run reporter thread
        self.thread = threading.Thread(target=self.run, name="AprsIsIgate", daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread is not None:
            while not self.queue.empty():
                self.queue.get(timeout=1)
                self.queue.task_done()
            self.queue.put(PoisonPill)

    def spot(self, spot):
        if spot["source"] != "AIS" or self.isConfigured():
            return
        callsign = Config.get()["aprs_callsign"].strip()
        try:
            self.queue.put(self.addIgatePath(self.buildTnc2Line(spot), callsign))
        except Exception:
            logger.exception("Failed to build APRS-IS packet")

    def getSupportedModes(self):
        return ["PACKET"]

    def isConfigured(self):
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

    def buildTnc2Line(self, data):
        src = data.get("source", "")
        dst = data.get("destination", "")
        path = data.get("path", [])
        info = data.get("data", b"")
        if isinstance(info, bytes):
            info = info.decode(encoding, "replace")
        if dst:
            path.insert(0, dst)
        path = ",".join(path)
        return f"{source}>{path}:{info}"

    def addIgatePath(self, line, igateCallsign):
        if not igateCallsign:
            return line
        upper = line.upper()
        colon = line.find(":")
        if ",QAO," in upper or ",QAR," in upper or colon < 0:
            return line
        return line[:colon] + ",qAO," + igateCallsign + line[colon:]

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
            if not self.connect():
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
            self._socket = None

    def connect(self):
        if self.socket is not None:
            return True

        pm = Config.get()
        try:
            host = pm["aprs_igate_server"].strip()
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

        callsign = pm["aprs_callsign"].strip(),
        password = str(pm["aprs_igate_password"]).strip(),
        software = "OpenWebRX " + openwebrx_version
        login    = f"user {callsign} pass {password} vers {software}\r\n"

        try:
            sock = socket.create_connection((host, port), timeout = 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(login.encode("ascii"))
            sock.settimeout(2)
            try:
                sock.recv(4096)
            except socket.timeout:
                pass
            sock.settimeout(None)
            self.socket = sock
            logger.info("Connected to APRS-IS server %s:%d as %s", host, port, callsign)
            return True
        except OSError:
            logger.warning("Could not connect to APRS-IS server %s:%d", host, port)
            self.disconnect()
            return False
