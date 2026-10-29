import gzip
import json
import logging
import threading
import time
from datetime import datetime
from email.utils import formatdate
from queue import Empty, Full, Queue
from urllib import error, request

from owrx.config import Config
from owrx.metrics import CounterMetric, Metrics
from owrx.reporting.reporter import FilteredReporter
from owrx.version import openwebrx_version

logger = logging.getLogger(__name__)

PoisonPill = object()

SOFTWARE_NAME = "OpenWebRX"
SELF_SPOT_SECONDS = 3600 * 6

MANUFACTURERS = {
    "RS41"  : "Vaisala",
    "DFM"   : "Graw",
    "M10"   : "Meteomodem",
    "M20"   : "Meteomodem",
    "MTS01" : "Meteosis",
}


class Worker(threading.Thread):
    telemetryEndpoint = "https://api.v2.sondehub.org/sondes/telemetry"
    listenerEndpoint = "https://api.v2.sondehub.org/listeners"
    standardUploadIntervalSeconds = 15.0
    dfmUploadIntervalSeconds = 30.0
    dfmMinPackets = 10
    uploadRetries = 5

    def __init__(self, queue: Queue, uploadCounter: CounterMetric, errorCounter: CounterMetric, selfUploadCounter: CounterMetric, selfErrorCounter: CounterMetric):
        self.doRun = True
        self.queue = queue
        self.uploadCounter = uploadCounter
        self.errorCounter = errorCounter
        self.selfUploadCounter = selfUploadCounter
        self.selfErrorCounter = selfErrorCounter
        self.standardBuffer = []
        self.dfmBuffer = []
        self.standardSeen = set()
        self.dfmSeen = set()
        self.nextStandardFlush = time.monotonic() + self.standardUploadIntervalSeconds
        self.nextDfmFlush = time.monotonic() + self.dfmUploadIntervalSeconds
        super().__init__(daemon=True, name="sondehub-uploader")

    def run(self):
        logger.info("Sondehub telemetry reporting started")
        while self.doRun:
            try:
                # Get next queued spot
                spot = self.queue.get()

                # Terminate if stopping
                if spot is PoisonPill:
                    self.doRun = False
                    self.queue.task_done()
                    break

                # Detect and upload own position reports
                if "type" not in spot:
                    self.uploadSelfSpot(spot)
                    continue

                # Determine where to buffer spot
                if spot["type"] == "DFM":
                    buffer = self.dfmBuffer
                    seen = self.dfmSeen
                else:
                    buffer = self.standardBuffer
                    seen = self.standardSeen

                # Deduplicate frames if possible
                if "serial" not in spot or "frame" not in spot:
                    buffer.add(spot)
                else:
                    key = (spot["serial"], spot["frame"])
                    if key not in seen:
                        buffer.add(spot)
                        seen.add(key)

                # Flush accumulated spots periodically
                now = time.monotonic()
                if now >= self.nextStandardFlush and len(self.standardBuffer) > 0:
                    self.uploadBatch(self.standardBuffer, "standard")
                    self.nextStandardFlush = now + self.standardUploadIntervalSeconds
                    self.standardBuffer.clear()
                    self.standardSeen.clear()
                if now >= self.nextDfmFlush and len(self.dfmBuffer) >= self.dfmMinPackets:
                    self.uploadBatch(self.dfmBuffer, "dfm")
                    self.nextDfmFlush = now + self.dfmUploadIntervalSeconds
                    self.dfmBuffer.clear()
                    self.dfmSeen.clear()

            except Empty:
                pass

        # Done with the worker thread
        logger.info("Sondehub telemetry reporting stopped")

    def uploadBatch(self, batch, batchType):
        # Prepare request body and headers
        body = gzip.compress(json.dumps(batch).encode("utf-8"))
        headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "Date": formatdate(timeval=None, localtime=False, usegmt=True),
            "User-Agent": "{0}-{1}".format(SOFTWARE_NAME.rstrip("+"), openwebrx_version.lstrip("v"))
        }
        # Send HTTP request
        if self.httpUpload(self.telemetryEndpoint, headers, body):
            self.uploadCounter.inc()
            logger.info("Sondehub batch upload succeeded type=%s packets=%d",
                batchType, len(batch)
            )
        else:
            self.errorCounter.inc()
            logger.error("Sondehub batch upload failed type=%s packets=%d",
                batchType, len(batch)
            )

    def uploadSelfSpot(self, spot):
        # Prepare request body and headers
        body = json.dumps(spot).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "{0}-{1}".format(SOFTWARE_NAME.rstrip("+"), openwebrx_version.lstrip("v"))
        }
        # Send HTTP request
        if self.httpUpload(self.listenerEndpoint, headers, body):
            self.selfUploadCounter.inc()
            logger.info("Sondehub listener report upload succeeded")
        else:
            self.selfErrorCounter.inc()
            logger.error("Sondehub listener report upload failed")

    def httpUpload(self, url, headers, body):
        # Try sending HTTP request multiple times
        for attempt in range(1, self.uploadRetries + 1):
            responseText = ""
            status = None
            try:
                req = request.Request(url, data=body, headers=headers, method="PUT")
                with request.urlopen(req, timeout=60) as response:
                    status = getattr(response, "status", None)
                    responseText = response.read().decode("utf-8", errors="replace")
                break

            # If HTTP error occurred...
            except error.HTTPError as e:
                responseText = e.read().decode("utf-8", errors="replace")
                status = e.code
                if 500 <= e.code < 600 and attempt < self.uploadRetries:
                    logger.warning(
                        "Sondehub upload server error (attempt %d/%d): %s",
                        attempt, self.uploadRetries, responseText
                    )
                    time.sleep(1)
                else:
                    logger.error("Sondehub upload failed with status=%s response=%s",
                        status, responseText
                    )
                    return False

            # If non-HTTP error occurred, drop out
            except Exception as e:
                logger.exception("Sondehub upload failed: %s", str(e))
                return False

        # Success
        return True


class SondehubReporter(FilteredReporter):
    def __init__(self):
        self.queue = Queue(500)
        self.worker = None
        self.callsign = None
        self.lastSelfSpot = 0
        # Create reporting metrics
        metrics = Metrics.getSharedInstance()
        self.spotCounter = CounterMetric()
        metrics.addMetric("sondehub.spots", self.spotCounter)
        self.uploadCounter = CounterMetric()
        metrics.addMetric("sondehub.uploads", self.uploadCounter)
        self.errorCounter = CounterMetric()
        metrics.addMetric("sondehub.errors", self.errorCounter)
        self.selfUploadCounter = CounterMetric()
        metrics.addMetric("sondehub.self_uploads", self.selfUploadCounter)
        self.selfErrorCounter = CounterMetric()
        metrics.addMetric("sondehub.self_errors", self.selfErrorCounter)
        # Subscribe to config changes
        self.configSub = Config.get().filter(
            "sondehub_enabled",
            "sondehub_callsign"
        ).wire(self.onConfigChanged)
        # Perform initial configuration
        self.onConfigChanged()

    def getSupportedModes(self):
        return ["SONDE"]

    # Parse and report sonde spots
    def spot(self, spot):
        # Must have reporting enabled
        if not self.callsign or not self.worker:
            return
        # Queue up the spot
        data = self.parseSpot(spot)
        if data is not None:
            try:
                self.queue.put(data, block=False)
                self.spotCounter.inc()
            except Full:
                logger.warning("Sondehub queue overflow, one telemetry frame lost")
                self.errorCounter.inc()
        # Periodically report our own position
        now = time.monotonic()
        if now - self.lastSelfSpot < SELF_SPOT_SECONDS:
            return
        # Queue up self-spot
        data = self.selfSpot()
        if data is not None:
            try:
                self.queue.put(data, block=False)
                self.selfSpotCounter.inc()
                self.lastSelfSpot = now
            except Full:
                logger.warning("Sondehub queue overflow, one self reporting frame lost")
                self.selfErrorCounter.inc()

    # Check field value for validity
    def isValidValue(self, field, value):
        # Convert value to floating point
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        # Check for validity based on field type
        if field == "temp":
            return value > -273.0
        elif field == "humidity":
            return value >= 0.0
        elif field == "pressure":
            return value > 0.0
        elif field == "batt":
            return value >= 0.0
        else:
            return False

    # Get our own position in reportable format
    def getOurPosition(self):
        config = Config.get()
        position = config["receiver_gps"]
        altitude = config["receiver_asl"] if "receiver_asl" in config else 0
        return [position["lat"], position["lon"], altitude]

    # Get sonde type
    def parseType(self, data):
        # Get type and subtype
        type    = data["type"].upper() if "type" in data else ""
        subtype = data["subtype"].upper() if "subtype" in data else ""
        family  = ""
        # Guess device family
        if type.startswith("DFM") or ":DFM" in subtype:
            family = "DFM"
        elif "rs41_mainboard" in data:
            family = "RS41"
        else:
            for x in ["RS41", "DFM", "M10", "M20", "MTS01"]:
                if type == x or subtype.startswith(x):
                    family = x
                    break
        # Parse DFM subtype
        if family == "DFM" and ":" in subtype:
            subtype = subtype.split(":", 1)[1]
        # Return family, type, subtype
        return family, type or family or None, subtype or None

    # Convert spotted data into reported data
    def parseSpot(self, spot):
        # Must have data and callsign
        if not self.callsign or "data" not in spot:
            return None
        # Determine sonde family and type
        data = spot["data"]
        family, type, subtype = self.parseType(data)
        if family is None or type is None:
            return None
        # Determine serial number
        serial = str(data["id"]) if "id" in data else ""
        if not serial or serial.lower() == "xxxxxxxx":
            return None
        # Compose data to report
        out = {
            "software_name"     : SOFTWARE_NAME,
            "software_version"  : openwebrx_version.lstrip("v"),
            "uploader_callsign" : self.callsign,
            "time_received"     : datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "manufacturer"      : MANUFACTURERS.get(family, "Unknown"),
            "serial"            : serial,
            "frequency"         : spot.get("freq", 403000000) / 1000000,
            "type"              : type,
            "uploader_position" : self.getOurPosition()
        }
        # Add subtype
        if subtype:
            out["subtype"] = subtype
        # Copy some fields over
        for field in ["datetime", "lat", "lon", "alt", "vel_h", "vel_v", "heading", "frame", "sats", "batt"]:
            if field in data:
                out[field] = data[field]
        # Validate some fields before copying them
        for field in ["temp", "humidity", "pressure", "batt"]:
            if field in data and self.isValidValue(field, data[field]):
                out[field] = data[field]
        # Done
        return out

    # Report own location
    def selfSpot(self):
        # Must have callsign
        if not self.callsign:
            return None
        # Get antenna desctiption
        config = Config.get()
        antenna = config["sondehub_antenna"] if "sondehub_antenna" in config else ""
        # Create own position report
        return {
            "software_name": SOFTWARE_NAME,
            "software_version": openwebrx_version.lstrip("v"),
            "uploader_callsign": self.callsign,
            "uploader_position": self.getOurPosition(),
            "uploader_radio": SOFTWARE_NAME,
            "uploader_antenna": antenna,
            "mobile": False,
        }

    def onConfigChanged(self, *args):
        # Get Sondehub callsign, set to None if disabled or empty
        config = Config.get()
        if not config["sondehub_enabled"]:
            self.callsign = None
        else:
            self.callsign = config["sondehub_callsign"]
            if not self.callsign or self.callsign == "N0CALL":
                self.callsign = None
        # Start/stop workers when enabled/disabled
        if self.callsign is not None and self.worker is None:
            self.queue = Queue(500)
            self.worker = Worker(self.queue, self.uploadCounter, self.errorCounter, self.selfUploadCounter, self.selfErrorCounter)
            self.worker.start()
        elif self.worker is not None:
            self._stopWorker()

    def stop(self):
        if self.configSub is not None:
            self.configSub.cancel()
            self.configSub = None
        if self.worker is not None:
            self._stopWorker()

    def _stopWorker(self):
        while not self.queue.empty():
            try:
                self.queue.get(timeout=1)
                self.queue.task_done()
            except Exception:
                break
        self.queue.put(PoisonPill)
        self.worker.join(timeout=5)
        self.worker = None
