from owrx.toolbox import TextParser
from owrx.reporting import ReportingEngine
from owrx.aprs import AprsParser, thirdpartyeRegex

import base64
import json

import logging

logger = logging.getLogger(__name__)


class LoraParser(TextParser):
    def __init__(self, service: bool = False):
        # Construct parent object
        super().__init__(filePrefix="LORA", service=service)
        self.aprsParser = AprsParser()

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
        self.aprsParser.setDialFrequency(frequency)

    def parse(self, msg: bytes):
        try:
            # Try parsing as JSON first
            out = json.loads(msg)
        except Exception as e:
            # Not JSON, return as string
            return msg.decode("utf-8") + "\n"

        # Add mode name
        out["mode"] = "LORA"

        # Add frequency, if known
        if self.frequency:
            out["freq"] = self.frequency

        # Try decoding payload
        if "payload" in out:
            try:
                payload = self.parsePayload(out, base64.b64decode(out["payload"]))
                if payload:
                    return payload
            except Exception as e:
                logger.error("Exception parsing LoRa payload: %s", str(e))

        # Report message
        ReportingEngine.getSharedInstance().spot(out)

        # Return JSON data
        return out

    # Parse LoRa payload by type
    def parsePayload(self, out, data: bytes):
        if len(data) > 3 and data[0] == 0x3C and data[1] == 0xFF and data[2] == 0x01:
            return self.parseAprs(out, data[3:])
        else:
            return None

    # Parse LoRa APRS payload
    def parseAprs(self, out, data: bytes):
        payload = data.decode("utf-8").strip()
        matches = thirdpartyeRegex.match(payload)
        if not matches:
            logger.warning("Couldn't parse LoRa APRS payload: '%s'", text)
        else:
            path = matches.group(2).split(",")
            info = matches.group(6)
            if "\x00" in info:
                info = info.split("\x00", 1)[0]
            return self.aprsParser.process({
                "source"      : matches.group(1).upper(),
                "destination" : path[0] if path else "",
                "path"        : path[1:] if len(path) > 1 else [],
                "data"        : info.encode("utf-8"),
                "raw"         : "".join("{:02X}".format(x) for x in data),
            })
