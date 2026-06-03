import json
import logging
from owrx.toolbox import TextParser

logger = logging.getLogger(__name__)


class TetraParser(TextParser):

    def __init__(self, service: bool = False):
        super().__init__(filePrefix="TETRA", service=service)

    def parse(self, line: bytes) -> dict | None:
        try:
            text = line.decode("ascii", errors="replace").strip()
        except Exception:
            return None

        if not text:
            return None

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("TetraParser: not valid JSON: %r", text)
            return None

        if not isinstance(data, dict):
            return None

        return self._map(data)

    def _map(self, data: dict) -> dict | None:
        """Map a raw tetrarx JSON dict to the OpenWebRX internal format."""
        if "FTYP" not in data:
            return None

        out: dict = {"mode": "TETRA", "ft": int(data["FTYP"])}

        if self.frequency:
            out["freq"] = self.frequency

        # Signal quality
        if "dB" in data:
            out["rfdb"] = float(data["dB"])
        if "AFC" in data:
            out["offset"] = int(data["AFC"])
        if "EYE" in data:
            out["eye"] = int(data["EYE"])

        # Timeslot / frame / multiframe counters
        if "TN" in data:
            out["tn"] = int(data["TN"])
        if "FN" in data:
            out["fn"] = int(data["FN"])
        if "MN" in data:
            out["mn"] = int(data["MN"])

        # Network code: CC = "MCC,MNC,BCC"
        if "CC" in data:
            parts = str(data["CC"]).split(",")
            if len(parts) == 3:
                try:
                    out["mcc"] = int(parts[0])
                    out["mnc"] = int(parts[1])
                    out["bcc"] = int(parts[2])
                except ValueError:
                    logger.debug("TetraParser: malformed CC: %r", data["CC"])

        # TX / RX frequencies
        if "TX" in data:
            out["tx_mhz"] = float(data["TX"])
        if "RX" in data:
            out["rx_mhz"] = float(data["RX"])

        # Location area / MS transmit power
        if "LA" in data:
            out["la"] = int(data["LA"])
        if "Po" in data:
            out["power_dbm"] = int(data["Po"])

        # Service flags
        if data.get("VOICE"):
            out["voice_service"] = True
        if data.get("ENC"):
            out["air_encrypted"] = True
        if data.get("AUDIO"):
            out["audio"] = True

        # Subscriber identity
        if "ssi" in data:
            out["ssi"] = [int(data["ssi"])]

        # Addressing (traffic frames)
        if "ADRTYP" in data:
            out["adr_type"] = int(data["ADRTYP"])
        if "MAC" in data:
            out["mac"] = int(data["MAC"])

        # Only output data when there is Voice traffic
        if data.get("AUDIO") == 1:
            out["air_encrypted"] = False
            return out
        else:
            return None

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
