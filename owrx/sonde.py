from owrx.toolbox import TextParser
import json

import logging

logger = logging.getLogger(__name__)


class SondeParser(TextParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="SONDE", service=service)

    def parse(self, msg: bytes):
        # Do not parse in service mode
        if self.service:
            return None
        # Expect JSON data in text form
        try:
            data = json.loads(msg)
        except Exception:
            # Raw data....
            logger.debug("Not JSON, assuming raw data...")
            data = { "raw" : msg.decode("utf-8") }
        data["mode"] = "SONDE"
        return data

