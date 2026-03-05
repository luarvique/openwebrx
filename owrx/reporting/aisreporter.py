import logging
import threading
import socket

from owrx.config import Config
from owrx.metrics import Metrics, CounterMetric
from owrx.reporting.reporter import FilteredReporter

logger = logging.getLogger(__name__)

# ITU-R M.1371 caps a VDM sentence at 82 characters including delimiters.
# Allow a small margin for any framing bytes added in transit.
_MAX_DATAGRAM_SIZE = 100


class AisReporter(FilteredReporter):

    def getSupportedModes(self):
        return ["AIS"]

    def __init__(self):
        self._stopped = False
        # _state_lock serialises stop() against spot().  Uploader._lock is
        # always acquired *after* _state_lock, so callers must never invert
        # that order or a deadlock will result.
        self._state_lock = threading.Lock()

        # Initialise to None before attempting construction so the attribute
        # always exists even if Uploader() raises (e.g. invalid config).
        # spot() and stop() both guard against self.uploader being None.
        self.uploader = None
        try:
            self.uploader = Uploader()
        except Exception:
            logger.exception("AisReporter: failed to create uploader; spots will not be forwarded")

        self.sentCounter = None
        self.errorCounter = None

        try:
            metrics = Metrics.getSharedInstance()

            if not metrics.hasMetric("aisreporter.ais_sentences"):
                metrics.addMetric("aisreporter.ais_sentences", CounterMetric())

            if not metrics.hasMetric("aisreporter.errors"):
                metrics.addMetric("aisreporter.errors", CounterMetric())

            self.sentCounter = metrics.getMetric("aisreporter.ais_sentences")
            self.errorCounter = metrics.getMetric("aisreporter.errors")

        except Exception:
            logger.exception("Failed to register AisReporter metrics")

    def stop(self):
        with self._state_lock:
            self._stopped = True
            if self.uploader is not None:
                try:
                    self.uploader.close()
                except Exception:
                    logger.exception("Error while stopping AisReporter")

    def spot(self, spot):
        with self._state_lock:
            if self._stopped:
                return

        try:
            logger.debug("AisReporter received spot: %s", spot)

            if self.uploader is None:
                logger.error("AisReporter has no uploader; spots cannot be forwarded until the configuration is corrected")
                return

            if not isinstance(spot, dict):
                logger.warning("AisReporter dropping spot: expected dict, got %s", type(spot))
                return

            # Defensive mode validation even if FilteredReporter already filters
            if spot.get("mode") != "AIS":
                logger.warning("AisReporter dropping spot: unexpected mode %r", spot.get("mode"))
                return

            # Only forward spots that carry a raw NMEA sentence. OWRX also
            # emits 'object' type spots on the same bus — these are internal
            # re-encodings of already-forwarded AIS data into APRS format.
            # Other unknown types are logged at debug in case new spot types
            # are introduced in future.
            if spot.get("type") != "nmea":
                if spot.get("type") != "object":
                    logger.debug(
                        "AisReporter dropping spot: unexpected type %r", spot.get("type")
                    )
                return

            sentence = self._extract_nmea(spot)
            if not sentence:
                logger.warning("AisReporter dropping spot: could not extract NMEA sentence from spot %s", spot)
                return

            normalised = self._normalise_sentence(sentence)
            if not normalised:
                logger.warning("AisReporter dropping spot: could not normalise sentence %r", sentence)
                return

            self.uploader.upload(normalised)
            logger.info("Spot reported succesfully")

            if self.sentCounter:
                self.sentCounter.inc()

        except Exception:
            if self.errorCounter:
                self.errorCounter.inc()
            logger.exception("Unhandled exception while processing AIS spot")

    def _extract_nmea(self, spot):
        """
        Extract the raw NMEA sentence from a spot dict.

        The spot's 'raw' field contains an AX.25 frame as a hex string.
        The NMEA sentence begins at the first occurrence of '!AIVDM' or
        '!AIVDO' within that frame.  The 'message' field holds the decoded
        AIS payload bitstream, which is not what we want to forward.
        """
        try:
            raw_hex = spot.get("raw")
            if not isinstance(raw_hex, str) or not raw_hex:
                logger.warning("AisReporter: spot has missing or invalid 'raw' field: %r", raw_hex)
                return None

            data = bytes.fromhex(raw_hex)

            for marker in (b"!AIVDM", b"!AIVDO"):
                idx = data.find(marker)
                if idx != -1:
                    return data[idx:].decode("ascii").strip()

            logger.warning(
                "AisReporter: no AIVDM/AIVDO marker found in raw frame: %r", raw_hex
            )
            return None

        except Exception:
            logger.exception("Failed to extract NMEA sentence from spot")
            return None

    def _normalise_sentence(self, sentence):
        """
        Validate and normalise a single AIS NMEA sentence.

        Multi-part VDM messages (fragment count > 1) are rejected: forwarding
        an isolated fragment without its companions would produce malformed
        data at the receiver.  The assumption is that the upstream decoder
        emits fully assembled, single-sentence payloads; if that changes this
        method will need revisiting.

        A sentence whose checksum does not match its payload is treated as
        corrupt and dropped.  We never silently "correct" a bad checksum
        because the mismatch indicates that the payload itself may have been
        corrupted in transit.
        """
        try:
            s = sentence.strip()
            if not s:
                logger.debug("AisReporter: empty sentence after strip")
                return None

            if not (s.startswith("!AIVDM") or s.startswith("!AIVDO")):
                logger.debug("AisReporter: sentence does not start with !AIVDM or !AIVDO: %r", s)
                return None

            body, _, checksum_part = s.partition("*")

            fields = body.split(",")
            # Minimum VDM fields: !AIVDM,count,index,seq,channel,payload,pad
            if len(fields) < 7:
                logger.warning("AisReporter: sentence has too few fields (%d): %r", len(fields), s)
                return None

            # Reject fragmented messages — we only forward complete sentences.
            try:
                total_fragments = int(fields[1])
            except (ValueError, IndexError):
                logger.warning("AisReporter: sentence has non-integer fragment count: %r", s)
                return None

            if total_fragments != 1:
                logger.debug(
                    "AIS sentence is fragment %s of %s, dropping incomplete multi-part message",
                    fields[2],
                    fields[1],
                )
                return None

            # Compute the correct XOR checksum over the body (excluding the
            # leading '!').
            checksum = 0
            for c in body[1:]:
                checksum ^= ord(c)
            calculated = f"{checksum:02X}"

            if checksum_part:
                provided = checksum_part[:2].upper()
                if len(provided) == 2 and provided != calculated:
                    logger.warning(
                        "AIS checksum mismatch (provided=%s calculated=%s), dropping sentence",
                        provided,
                        calculated,
                    )
                    return None

            return f"{body}*{calculated}\r\n"

        except Exception:
            logger.exception("Failed to normalise AIS sentence")
            return None


class Uploader:

    def __init__(self):
        self._lock = threading.Lock()
        self._closed = False

        pm = Config.get()

        try:
            # Both keys are guaranteed present by defaults.py, so direct
            # subscript access is correct; no fallback logic is needed here.
            host = pm["aisreporter_udp_host"]
            port = pm["aisreporter_udp_port"]

            if not isinstance(host, str) or not host:
                raise ValueError(f"Invalid aisreporter_udp_host: {host!r}")

            port = int(port)
            if not (0 < port < 65536):
                raise ValueError(f"Invalid aisreporter_udp_port: {port!r}")

            self.host = host
            self.port = port

            # A plain UDP socket.  sendto() on an unconnected UDP socket does
            # not block waiting for a reply, so no timeout is needed or useful.
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        except Exception:
            logger.exception("Failed to initialise AisReporter UDP uploader")
            raise

    def upload(self, sentence):
        with self._lock:
            if self._closed:
                return

            try:
                if not isinstance(sentence, str):
                    return

                # Non-ASCII bytes indicate upstream corruption; log and drop
                # rather than silently mangling the payload.
                try:
                    data = sentence.encode("ascii")
                except UnicodeEncodeError:
                    logger.warning(
                        "AIS sentence contains non-ASCII characters, dropping: %r",
                        sentence,
                    )
                    return

                if not data or len(data) > _MAX_DATAGRAM_SIZE:
                    logger.warning(
                        "AIS sentence has unexpected length %d, dropping", len(data)
                    )
                    return

                self.socket.sendto(data, (self.host, self.port))
                logger.debug("AIS sentence sent to %s:%d: %r", self.host, self.port, sentence)

            except OSError:
                logger.exception("Socket error while sending AIS sentence")
            except Exception:
                logger.exception("Unexpected error while sending AIS sentence")

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True

            try:
                self.socket.close()
            except Exception:
                logger.exception("Failed to close AisReporter UDP socket")