import logging


logger = logging.getLogger(__name__)


class TetraParser(object):
    def __init__(self):
        self.frequency = 0

    def setDialFrequency(self, frequency: int) -> None:
        self.frequency = frequency

    def parse(self, data: dict):
        #logger.info("data: %s", data)
        # Must have FTYP
        if "FTYP" not in data:
            return None

        # Only output data when there is voice traffic
        if "AUDIO" not in data or data["AUDIO"] != 1:
            return None

        # Start parsing
        out = { "mode": "TETRA", "ft": int(data["FTYP"]) }

        # Current frequency
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
                    logger.debug("Malformed CC: %r", data["CC"])

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
        if "VOICE" in data:
            out["voice_service"] = data["VOICE"] == 1
        if "ENC" in data:
            out["air_encrypted"] = data["ENC"] == 1
        if "AUDIO" in data:
            out["audio"] = data["AUDIO"] == 1

        # Subscriber identity
        if "ssi" in data:
            out["ssi"] = [int(data["ssi"])]

        # Addressing (traffic frames)
        if "ADRTYP" in data:
            out["adr_type"] = int(data["ADRTYP"])
        if "MAC" in data:
            out["mac"] = int(data["MAC"])

        # Done
        return out
