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

DFM_SUBTYPE_ALIASES = {
    "DFM9": "DFM09",
    "DFM09": "DFM09",
    "DFM09P": "DFM09P",
    "DFM17": "DFM17",
    "DFM06": "DFM06",
}

LISTENER_UPLOAD_INTERVAL_SECONDS = 3600 * 6 # 6 hours between station/listener location uploads

def getSoftwareVersion():
    return openwebrx_version.lstrip("v")


def getSoftwareUserAgent():
    return "{0}-{1}".format(SOFTWARE_NAME.rstrip("+"), getSoftwareVersion())


def getUploaderCallsign():
    config = Config.get()
    if "sondehub_callsign" in config and config["sondehub_callsign"]:
        return config["sondehub_callsign"]

    for key in ["aprs_callsign", "pskreporter_callsign", "wsprnet_callsign"]:
        if key in config and config[key] and config[key] != "N0CALL":
            return config[key]

    if "receiver_name" in config and config["receiver_name"] and config["receiver_name"] != "[Callsign]":
        return config["receiver_name"]

    return "N0CALL"


def getUploaderPosition():
    config = Config.get()
    position = config["receiver_gps"]
    if not hasattr(position, "__contains__") or not hasattr(position, "__getitem__"):
        return None

    if "lat" not in position or "lon" not in position:
        return None

    altitude = config["receiver_asl"] if "receiver_asl" in config else 0
    return [position["lat"], position["lon"], altitude]


def getListenerAntenna():
    config = Config.get()
    value = config["sondehub_antenna"] if "sondehub_antenna" in config else None
    return "" if value is None else str(value).strip()


def isSondehubTelemetryEnabled():
    return Config.get()["sondehub_enabled"]


class Worker(threading.Thread):
    endpoint = "https://api.v2.sondehub.org/sondes/telemetry"
    standardUploadIntervalSeconds = 15.0
    dfmUploadIntervalSeconds = 30.0
    dfmMinPackets = 10
    uploadRetries = 5

    def __init__(self, queue: Queue, uploadCounter: CounterMetric = None, errorCounter: CounterMetric = None):
        self.queue = queue
        self.doRun = True
        self.uploadCounter = uploadCounter
        self.errorCounter = errorCounter
        self.lock = threading.RLock()
        self.standardBuffer = []
        self.dfmBuffer = []
        self.standardSeen = set()
        self.dfmSeen = set()
        self.nextStandardFlush = time.monotonic() + self.standardUploadIntervalSeconds
        self.nextDfmFlush = time.monotonic() + self.dfmUploadIntervalSeconds
        super().__init__(daemon=True, name="sondehub-uploader")

    def run(self):
        while self.doRun:
            try:
                spot = self.queue.get(timeout=1.0)
            except Empty:
                spot = None

            if spot is PoisonPill:
                self.doRun = False
                self.queue.task_done()
                break

            if spot is not None:
                try:
                    self._bufferSpot(spot)
                except Exception:
                    if self.errorCounter is not None:
                        self.errorCounter.inc()
                    logger.exception("Exception while buffering Sondehub telemetry")
                finally:
                    self.queue.task_done()

            self._flushDueBatches()

        self._flushAllBuffers()

    @staticmethod
    def _frameKey(entry):
        serial = entry.get("serial")
        frame = entry.get("frame")
        if serial is None or frame is None:
            return None
        return (str(serial), frame)

    def _bufferSpot(self, spot):
        entry = self._spotToEntry(spot)
        if entry is None:
            return

        with self.lock:
            if self._isDfmEntry(entry):
                buffer = self.dfmBuffer
                seen = self.dfmSeen
            else:
                buffer = self.standardBuffer
                seen = self.standardSeen

            key = self._frameKey(entry)
            if key is not None and key in seen:
                logger.debug(
                    "SondehubReporter dropping duplicate frame serial=%s frame=%s",
                    key[0],
                    key[1],
                )
                return

            buffer.append(entry)
            if key is not None:
                seen.add(key)

    def _flushDueBatches(self):
        now = time.monotonic()

        standardBatch = None
        dfmBatch = None

        with self.lock:
            if now >= self.nextStandardFlush and self.standardBuffer:
                standardBatch = self.standardBuffer
                self.standardBuffer = []
                self.standardSeen = set()
                self.nextStandardFlush = now + self.standardUploadIntervalSeconds
            elif now >= self.nextStandardFlush:
                self.nextStandardFlush = now + self.standardUploadIntervalSeconds

            if now >= self.nextDfmFlush:
                if len(self.dfmBuffer) >= self.dfmMinPackets:
                    dfmBatch = self.dfmBuffer
                    self.dfmBuffer = []
                    self.dfmSeen = set()
                self.nextDfmFlush = now + self.dfmUploadIntervalSeconds

        if standardBatch:
            self._uploadBatch(standardBatch, "standard")
        if dfmBatch:
            self._uploadBatch(dfmBatch, "dfm")

    def _flushAllBuffers(self):
        with self.lock:
            standardBatch = self.standardBuffer
            dfmBatch = self.dfmBuffer if len(self.dfmBuffer) >= self.dfmMinPackets else []
            self.standardBuffer = []
            self.standardSeen = set()
            self.dfmBuffer = [] if dfmBatch else self.dfmBuffer
            if dfmBatch:
                self.dfmSeen = set()

        if standardBatch:
            self._uploadBatch(standardBatch, "standard")
        if dfmBatch:
            self._uploadBatch(dfmBatch, "dfm")

    @staticmethod
    def _getSondeFamily(data):
        sonde_type = str(data.get("type", "")).upper()
        subtype = str(data.get("subtype", "")).upper()

        if sonde_type == "RS41" or subtype.startswith("RS41") or "rs41_mainboard" in data:
            return "rs41"
        if sonde_type == "DFM" or sonde_type.startswith("DFM") or subtype.startswith("DFM") or ":DFM" in subtype:
            return "dfm"
        if sonde_type == "M10" or subtype == "M10" or subtype.startswith("M10"):
            return "m10"
        if sonde_type == "M20" or subtype == "M20" or subtype.startswith("M20"):
            return "m20"
        if sonde_type == "MTS01" or subtype == "MTS01" or subtype.startswith("MTS01"):
            return "mts01"
        return None

    @staticmethod
    def _parseDfmSubtype(subtype_raw):
        if not subtype_raw:
            return None

        subtype = subtype_raw.strip()
        if ":" in subtype:
            subtype = subtype.split(":", 1)[1].strip()

        alias = DFM_SUBTYPE_ALIASES.get(subtype.upper())
        return alias if alias is not None else subtype

    @staticmethod
    def _normalizeTypeAndSubtype(data):
        family = Worker._getSondeFamily(data)
        subtype_raw = str(data.get("subtype", "")).strip()

        if family == "rs41":
            sonde_type = str(data.get("type", "")).strip().upper() or "RS41"
            return sonde_type, subtype_raw or None

        if family == "dfm":
            return "DFM", Worker._parseDfmSubtype(subtype_raw)

        if family == "m10":
            return "M10", "M10"

        if family == "m20":
            return "M20", "M20"

        if family == "mts01":
            return "MTS01", subtype_raw or None

        return None, None

    @staticmethod
    def _getManufacturer(family):
        if family == "rs41":
            return "Vaisala"
        if family in ("dfm", "m10", "m20"):
            return "MeteoModem"
        if family == "mts01":
            return "Meteosis"
        return "Unknown"

    @staticmethod
    def _isSupportedData(data):
        return Worker._getSondeFamily(data) is not None

    @staticmethod
    def _isDfmFamily(data):
        return Worker._getSondeFamily(data) == "dfm"

    @staticmethod
    def _isDfmEntry(entry):
        return str(entry.get("type", "")).upper() == "DFM"

    @staticmethod
    def _isValidSerial(data, family):
        serial = str(data.get("id", "")).strip()
        if not serial:
            return False
        if family == "dfm" and serial.lower() == "xxxxxxxx":
            return False
        return True

    @staticmethod
    def _isValidPtuValue(field, value):
        """Match radiosonde_auto_rx / SondeHub invalid PTU sentinels (see RS JSON wiki)."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False
        if field == "temp":
            return numeric > -273.0
        if field == "humidity":
            return numeric >= 0.0
        if field == "pressure":
            return numeric > 0.0
        return False

    @staticmethod
    def _addPtuFields(entry, data):
        """Copy valid PTU fields from any supported decoder JSON into SondeHub v2 telemetry."""
        for key in ("temp", "humidity", "pressure"):
            if key in data and Worker._isValidPtuValue(key, data[key]):
                entry[key] = data[key]

    @staticmethod
    def _subtypeTypicallyHasPressureSensor(data, family):
        """Best-effort hint for debug logs; decoders may still omit pressure until calibrated."""
        subtype = str(data.get("subtype", "")).upper()
        sonde_type = str(data.get("type", "")).upper()
        if family == "rs41":
            return "SGP" in subtype or sonde_type.startswith("RS92")
        if family == "dfm":
            return "DFM09P" in subtype or subtype.endswith("09P")
        if family in ("m10", "m20", "mts01"):
            return True
        return False

    def _spotToEntry(self, spot):
        if not isinstance(spot, dict):
            logger.warning("SondehubReporter dropping spot: expected dict, got %s", type(spot))
            return None

        data = spot.get("data", {})
        if not isinstance(data, dict):
            logger.warning("SondehubReporter dropping spot without decoder data payload")
            return None

        if not self._isSupportedData(data):
            return None

        family = self._getSondeFamily(data)
        if not self._isValidSerial(data, family):
            if family == "dfm":
                logger.debug("SondehubReporter waiting for DFM serial before upload")
            return None

        now = datetime.utcnow()
        sonde_type, subtype = self._normalizeTypeAndSubtype(data)
        if sonde_type is None:
            return None

        manufacturer = self._getManufacturer(family)

        entry = {
            "software_name": SOFTWARE_NAME,
            "software_version": getSoftwareVersion(),
            "uploader_callsign": getUploaderCallsign(),
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

        uploader_position = getUploaderPosition()
        if uploader_position is not None:
            entry["uploader_position"] = uploader_position

        if "sats" in data:
            entry["sats"] = data["sats"]
        if "batt" in data and data.get("batt", -1) >= 0:
            entry["batt"] = data["batt"]
        self._addPtuFields(entry, data)
        if subtype:
            entry["subtype"] = subtype

        raw_pressure = data.get("pressure")
        if "pressure" in entry:
            logger.debug(
                "Sondehub PTU pressure included type=%s subtype=%s serial=%s frame=%s pressure=%s hPa",
                sonde_type,
                subtype or "",
                entry.get("serial"),
                entry.get("frame"),
                entry["pressure"],
            )
        elif Worker._subtypeTypicallyHasPressureSensor(data, family):
            logger.debug(
                "Sondehub PTU pressure missing type=%s subtype=%s serial=%s frame=%s raw=%s "
                "(sonde may lack sensor or calibration not complete)",
                sonde_type,
                data.get("subtype", ""),
                entry.get("serial"),
                entry.get("frame"),
                raw_pressure,
            )
        elif raw_pressure is not None and not Worker._isValidPtuValue("pressure", raw_pressure):
            logger.debug(
                "Sondehub PTU pressure invalid type=%s subtype=%s raw=%s",
                sonde_type,
                data.get("subtype", ""),
                raw_pressure,
            )

        return entry

    def _uploadBatch(self, batch, batchType):
        if not batch:
            return

        logger.debug(
            "Sondehub pushing %s batch to API packets=%d uploader=%s",
            batchType,
            len(batch),
            batch[0].get("uploader_callsign"),
        )
        logger.debug("Sondehub telemetry batch payload: %s", batch)
        pressure_frames = [
            (e.get("serial"), e.get("frame"), e.get("pressure"))
            for e in batch
            if e.get("pressure") is not None
        ]
        if pressure_frames:
            logger.debug(
                "Sondehub batch includes pressure in %d packet(s): %s",
                len(pressure_frames),
                pressure_frames,
            )

        body = gzip.compress(json.dumps(batch).encode("utf-8"))
        headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "Date": formatdate(timeval=None, localtime=False, usegmt=True),
            "User-Agent": getSoftwareUserAgent(),
        }

        status = None
        responseText = ""
        for attempt in range(1, self.uploadRetries + 1):
            try:
                req = request.Request(self.endpoint, data=body, headers=headers, method="PUT")
                with request.urlopen(req, timeout=60) as response:
                    status = getattr(response, "status", None)
                    responseText = response.read().decode("utf-8", errors="replace")
                break
            except error.HTTPError as e:
                status = e.code
                responseText = e.read().decode("utf-8", errors="replace")
                if 500 <= e.code < 600 and attempt < self.uploadRetries:
                    logger.warning(
                        "Sondehub batch upload server error (attempt %d/%d): %s",
                        attempt,
                        self.uploadRetries,
                        responseText,
                    )
                    time.sleep(1)
                    continue
                if self.errorCounter is not None:
                    self.errorCounter.inc()
                logger.error(
                    "Sondehub batch upload failed type=%s packets=%d status=%s response=%s",
                    batchType,
                    len(batch),
                    status,
                    responseText,
                )
                return
            except Exception:
                if self.errorCounter is not None:
                    self.errorCounter.inc()
                logger.exception(
                    "Sondehub batch upload failed type=%s packets=%d",
                    batchType,
                    len(batch),
                )
                return

        if self.uploadCounter is not None:
            self.uploadCounter.inc()

        logger.info(
            "Sondehub uploaded %s batch packets=%d status=%s uploader=%s",
            batchType,
            len(batch),
            status if status is not None else "unknown",
            batch[0].get("uploader_callsign"),
        )
        if responseText:
            logger.debug("Sondehub telemetry batch response: %s", responseText)


class ListenerWorker(threading.Thread):
    endpoint = "https://api.v2.sondehub.org/listeners"
    uploadRetries = 5

    def __init__(self, uploadCounter: CounterMetric = None, errorCounter: CounterMetric = None):
        self.doRun = True
        self.uploadCounter = uploadCounter
        self.errorCounter = errorCounter
        super().__init__(daemon=True, name="sondehub-listener")

    def run(self):
        logger.info(
            "Sondehub listener worker started (upload every %d seconds)",
            LISTENER_UPLOAD_INTERVAL_SECONDS,
        )
        while self.doRun:
            try:
                if isSondehubTelemetryEnabled():
                    self.uploadListener()
            except Exception:
                logger.exception("Unhandled error in Sondehub listener worker")
            if not self._sleep(LISTENER_UPLOAD_INTERVAL_SECONDS):
                break
        logger.info("Sondehub listener worker stopped")

    def stop(self):
        self.doRun = False

    def _sleep(self, seconds):
        end = time.monotonic() + seconds
        while self.doRun and time.monotonic() < end:
            time.sleep(1)
        return self.doRun

    def uploadListener(self):
        position = getUploaderPosition()
        if position is None:
            logger.warning(
                "Sondehub listener upload skipped: configure receiver_gps and receiver_asl in General Settings"
            )
            return

        callsign = getUploaderCallsign()
        antenna = getListenerAntenna()
        logger.info(
            "Sondehub listener upload starting callsign=%s lat=%s lon=%s alt=%s antenna=%s",
            callsign,
            position[0],
            position[1],
            position[2],
            antenna if antenna else "(empty)",
        )

        payload = {
            "software_name": SOFTWARE_NAME,
            "software_version": getSoftwareVersion(),
            "uploader_callsign": callsign,
            "uploader_position": position,
            "uploader_radio": SOFTWARE_NAME,
            "uploader_antenna": getListenerAntenna(),
            "mobile": False,
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": getSoftwareUserAgent(),
        }

        status = None
        responseText = ""
        for attempt in range(1, self.uploadRetries + 1):
            try:
                req = request.Request(self.endpoint, data=body, headers=headers, method="PUT")
                with request.urlopen(req, timeout=60) as response:
                    status = getattr(response, "status", None)
                    responseText = response.read().decode("utf-8", errors="replace")
                break
            except error.HTTPError as e:
                status = e.code
                responseText = e.read().decode("utf-8", errors="replace")
                if 500 <= e.code < 600 and attempt < self.uploadRetries:
                    logger.warning(
                        "Sondehub listener upload server error (attempt %d/%d): %s",
                        attempt,
                        self.uploadRetries,
                        responseText,
                    )
                    time.sleep(1)
                    continue
                if self.errorCounter is not None:
                    self.errorCounter.inc()
                logger.error(
                    "Sondehub listener upload failed status=%s response=%s",
                    status,
                    responseText,
                )
                return
            except Exception:
                if self.errorCounter is not None:
                    self.errorCounter.inc()
                logger.exception("Sondehub listener upload failed")
                return

        if self.uploadCounter is not None:
            self.uploadCounter.inc()

        logger.info(
            "Sondehub listener position uploaded callsign=%s lat=%s lon=%s alt=%s status=%s",
            payload["uploader_callsign"],
            position[0],
            position[1],
            position[2],
            status if status is not None else "unknown",
        )
        logger.debug("Sondehub listener payload: %s", payload)
        if responseText:
            logger.debug("Sondehub listener response: %s", responseText)


class SondehubReporter(FilteredReporter):
    @staticmethod
    def _isSupportedSpot(spot):
        data = spot.get("data", {}) if isinstance(spot, dict) else {}
        if not isinstance(data, dict):
            return False
        return Worker._isSupportedData(data)

    def __init__(self):
        self.queue = Queue(500)
        metrics = Metrics.getSharedInstance()
        self.spotCounter = CounterMetric()
        metrics.addMetric("sondehub.spots", self.spotCounter)
        self.uploadCounter = CounterMetric()
        metrics.addMetric("sondehub.uploads", self.uploadCounter)
        self.errorCounter = CounterMetric()
        metrics.addMetric("sondehub.errors", self.errorCounter)
        self.listenerUploadCounter = CounterMetric()
        metrics.addMetric("sondehub.listener_uploads", self.listenerUploadCounter)
        self.listenerErrorCounter = CounterMetric()
        metrics.addMetric("sondehub.listener_errors", self.listenerErrorCounter)
        self.telemetryWorker = None
        self.listenerWorker = None
        self.configSub = Config.get().filter("sondehub_enabled").wire(self._applyConfig)
        self._applyConfig()

    def _applyConfig(self, *args):
        if isSondehubTelemetryEnabled():
            if self.telemetryWorker is None:
                self.queue = Queue(500)
                self.telemetryWorker = Worker(self.queue, self.uploadCounter, self.errorCounter)
                self.telemetryWorker.start()
                logger.info("Sondehub telemetry reporting started")
            if self.listenerWorker is None:
                self.listenerWorker = ListenerWorker(self.listenerUploadCounter, self.listenerErrorCounter)
                self.listenerWorker.start()
                logger.info(
                    "Sondehub listener reporting enabled (upload every %d seconds)",
                    LISTENER_UPLOAD_INTERVAL_SECONDS,
                )
        else:
            if self.telemetryWorker is not None:
                self._stopTelemetryWorker()
                logger.info("Sondehub telemetry reporting stopped")
            if self.listenerWorker is not None:
                self._stopListenerWorker()
                logger.info("Sondehub listener reporting stopped")

    def _stopTelemetryWorker(self):
        while not self.queue.empty():
            try:
                self.queue.get(timeout=1)
                self.queue.task_done()
            except Exception:
                break
        self.queue.put(PoisonPill)
        self.telemetryWorker.join(timeout=5)
        self.telemetryWorker = None

    def _stopListenerWorker(self):
        self.listenerWorker.stop()
        self.listenerWorker.join(timeout=5)
        self.listenerWorker = None

    def stop(self):
        if self.configSub is not None:
            self.configSub.cancel()
            self.configSub = None
        if self.telemetryWorker is not None:
            self._stopTelemetryWorker()
        if self.listenerWorker is not None:
            self._stopListenerWorker()

    def spot(self, spot):
        if not isSondehubTelemetryEnabled():
            return
        if self.telemetryWorker is None:
            return
        if not self._isSupportedSpot(spot):
            return
        try:
            self.queue.put(spot, block=False)
            self.spotCounter.inc()
        except Full:
            if self.errorCounter is not None:
                self.errorCounter.inc()
            logger.warning("Sondehub queue overflow, one telemetry frame lost")

    def getSupportedModes(self):
        return ["SONDE"]
