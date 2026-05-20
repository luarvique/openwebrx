from owrx.toolbox import TextParser

import base64
import json

import logging

logger = logging.getLogger(__name__)


class LoraParser(TextParser):
    def __init__(self, service: bool = False):
        # Construct parent object
        super().__init__(filePrefix="LORA", service=service)

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
        # Add your own LoRa payload parsers here

    def parseAprs(self, out, data: bytes):
        # Add APRS parser here
        pass
