import json
import logging
import threading
import time
from datetime import datetime
from queue import Full, Queue
from urllib import request

from owrx.config import Config
from owrx.metrics import CounterMetric, Metrics
from owrx.reporting.reporter import FilteredReporter
from owrx.version import openwebrx_version

logger = logging.getLogger(__name__)

PoisonPill = object()


class Worker(threading.Thread):
    endpoint = "https://api.v2.sondehub.org/sondes/telemetry"
    uploadIntervalSeconds = 15.0

    def __init__(self, queue: Queue, uploadCounter: CounterMetric = None, errorCounter: CounterMetric = None):
        self.queue = queue
        self.doRun = True
        self.uploadCounter = uploadCounter
        self.errorCounter = errorCounter
        self.nextUploadTimestamp = 0.0
        super().__init__(daemon=True)

    def run(self):
        while self.doRun:
            spot = self.queue.get()
            try:
                if spot is PoisonPill:
                    self.doRun = False
                else:
                    self.uploadSpot(spot)
            except Exception:
                if self.errorCounter is not None:
                    self.errorCounter.inc()
                logger.exception("Exception while uploading Sondehub telemetry")
            finally:
                self.queue.task_done()

    def _getUploaderCallsign(self):
        config = Config.get()
        if "sondehub_callsign" in config and config["sondehub_callsign"]:
            return config["sondehub_callsign"]

        for key in ["aprs_callsign", "pskreporter_callsign", "wsprnet_callsign"]:
            if key in config and config[key] and config[key] != "N0CALL":
                return config[key]

        if "receiver_name" in config and config["receiver_name"] and config["receiver_name"] != "[Callsign]":
            return config["receiver_name"]

        return "N0CALL"

    def _getSoftwareName(self):
        return "OpenWebRX - {0}".format(openwebrx_version.lstrip("v"))

    def _getUploaderPosition(self):
        config = Config.get()
        position = config["receiver_gps"]
        if not hasattr(position, "__contains__") or not hasattr(position, "__getitem__"):
            return None

        if "lat" not in position or "lon" not in position:
            return None

        altitude = config["receiver_asl"] if "receiver_asl" in config else 0
        return [position["lat"], position["lon"], altitude]

    def _isRs41(self, data):
        sonde_type = str(data.get("type", "")).upper()
        subtype = str(data.get("subtype", "")).upper()
        return sonde_type == "RS41" or subtype.startswith("RS41") or "rs41_mainboard" in data

    def _waitForUploadSlot(self):
        now = time.monotonic()
        waitSeconds = self.nextUploadTimestamp - now
        if waitSeconds > 0:
            time.sleep(waitSeconds)

    def uploadSpot(self, spot):
        if not isinstance(spot, dict):
            logger.warning("SondehubReporter dropping spot: expected dict, got %s", type(spot))
            return

        data = spot.get("data", {})
        if not isinstance(data, dict):
            logger.warning("SondehubReporter dropping spot without decoder data payload")
            return

        if not self._isRs41(data):
            return

        now = datetime.utcnow()

        sonde_type = str(data.get("type", "RS41")).upper()
        subtype = str(data.get("subtype", ""))

        type_map = {
            "RS41": "Vaisala",
            "RS92": "Vaisala",
            "RS92S": "Vaisala",
            "DFM": "MeteoModem",
            "M10": "MeteoModem",
            "M20": "MeteoModem",
        }

        manufacturer = type_map.get(sonde_type, "Unknown")
        if sonde_type.startswith("RS"):
            manufacturer = "Vaisala"

        entry = {
            "software_name": self._getSoftwareName(),
            "software_version": openwebrx_version.lstrip("v"),
            "uploader_callsign": self._getUploaderCallsign(),
            "time_received": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "manufacturer": manufacturer,
            "serial": str(data.get("id", "")),
            "datetime": data.get("datetime", ""),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "alt": data.get("alt"),
            "frequency": spot.get("freq", 403000000) / 1000000,
            "vel_h": data.get("vel_h"),
            "vel_v": data.get("vel_v"),
            "heading": data.get("heading"),
            "frame": data.get("frame"),
            "type": sonde_type,
        }

        uploader_position = self._getUploaderPosition()
        if uploader_position is not None:
            entry["uploader_position"] = uploader_position

        if "sats" in data:
            entry["sats"] = data["sats"]
        if "batt" in data:
            entry["batt"] = data["batt"]
        if "temp" in data:
            entry["temp"] = data["temp"]
        if subtype:
            entry["subtype"] = subtype

        payload = [entry]
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OpenWebRX+ Sondehub Reporter",
        }
        self._waitForUploadSlot()
        req = request.Request(self.endpoint, data=body, headers=headers, method="PUT")
        with request.urlopen(req, timeout=60) as response:
            status = getattr(response, "status", None)
        self.nextUploadTimestamp = time.monotonic() + self.uploadIntervalSeconds

        if self.uploadCounter is not None:
            self.uploadCounter.inc()

        logger.info(
            "RS41 uploaded to Sondehub serial=%s frame=%s freq=%s lat=%s lon=%s alt=%s uploader=%s status=%s",
            entry["serial"],
            entry.get("frame"),
            entry.get("frequency"),
            entry.get("lat"),
            entry.get("lon"),
            entry.get("alt"),
            entry.get("uploader_callsign"),
            status if status is not None else "unknown",
        )


class SondehubReporter(FilteredReporter):
    @staticmethod
    def _isRs41Spot(spot):
        data = spot.get("data", {}) if isinstance(spot, dict) else {}
        if not isinstance(data, dict):
            return False
        sonde_type = str(data.get("type", "")).upper()
        subtype = str(data.get("subtype", "")).upper()
        return sonde_type == "RS41" or subtype.startswith("RS41") or "rs41_mainboard" in data

    def __init__(self):
        self.queue = Queue(100)
        metrics = Metrics.getSharedInstance()
        self.spotCounter = CounterMetric()
        metrics.addMetric("sondehub.spots", self.spotCounter)
        self.uploadCounter = CounterMetric()
        metrics.addMetric("sondehub.uploads", self.uploadCounter)
        self.errorCounter = CounterMetric()
        metrics.addMetric("sondehub.errors", self.errorCounter)
        Worker(self.queue, self.uploadCounter, self.errorCounter).start()

    def stop(self):
        while not self.queue.empty():
            self.queue.get(timeout=1)
            self.queue.task_done()
        self.queue.put(PoisonPill)

    def spot(self, spot):
        if not self._isRs41Spot(spot):
            return
        try:
            self.queue.put(spot, block=False)
            self.spotCounter.inc()
        except Full:
            self.errorCounter.inc()
            logger.warning("Sondehub queue overflow, one telemetry frame lost")

    def getSupportedModes(self):
        return ["SONDE"]
