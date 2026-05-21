from owrx.toolbox import TextParser
from owrx.aprs import AprsParser, encoding, thirdpartyeRegex
from owrx.reporting import ReportingEngine

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
                self.parsePayload(out, base64.b64decode(out["payload"]))
            except Exception as e:
                logger.error("%s: Exception parsing: %s" % (self.myName(), str(e)))

        # Report message
        ReportingEngine.getSharedInstance().spot(out)

        # Return JSON data
        return out

    def parsePayload(self, out, data: bytes):
        if len(data) > 3 and data[0] == 0x3C and data[1] == 0xFF and data[2] == 0x01:
            self.parseAprs(out, data[3:])

    def parseAprs(self, out, data: bytes):
        text = data.decode(encoding, "replace").strip()
        matches = thirdpartyeRegex.match(text)
        if not matches:
            logger.warning("%s: could not parse LoRa APRS payload: %s", self.myName(), text)
            return

        path = matches.group(2).split(",")
        ax25 = {
            "source": matches.group(1).upper(),
            "destination": path[0] if path else "",
            "path": path[1:] if len(path) > 1 else [],
            "data": matches.group(6).encode(encoding),
            "raw": "".join("{:02X}".format(x) for x in data),
        }
        aprsData = self.aprsParser.process(ax25)
        if aprsData:
            out["aprs"] = aprsData
            logger.warning("%s: LoRa APRS parseAprs success: %s", self.myName(), aprsData)
