from owrx.toolbox import TextParser
from owrx.reporting import ReportingEngine
from owrx.map import Map, LatLngLocation
from datetime import datetime
import json

import logging

logger = logging.getLogger(__name__)


def getSymbolData(symbol, table):
    return {"symbol": symbol, "table": table, "index": ord(symbol) - 33, "tableindex": ord(table) - 33}


#
# This class represents current radiosonde location compatible with
# the APRS markers. It can be used for displaying radiosonde on the
# map.
#
class SondeLocation(LatLngLocation):
    def __init__(self, data):
        super().__init__(data["lat"], data["lon"])
        # Complete radiosonde data
        self.data = data

    def getSymbol(self):
        # Add an balloon symbol
        return getSymbolData("O", "/")

    def __dict__(self):
        res = super(SondeLocation, self).__dict__()
        # Keep all the data + an APRS-like symbol
        res["symbol"] = self.getSymbol()
        res.append(self.data)
        return res


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
            logger.debug("Not JSON, assuming raw data...")
            data = { "raw" : msg.decode("utf-8") }

        # Ignore "datetime" field for now ("%04d-%02d-%02dT%02d:%02d:%06.3fZ")
        out = {
            "mode"      : "SONDE",
            "timestamp" : round(datetime.now().timestamp() * 1000),
            "data"      : data
        }

        # Copy main attributes
        for x in ["id", "type", "subtype", "sats", "lat", "lon"]:
            if x in data:
                out[x] = data[x]

        # Convert some attributes
        if "alt" in data:
            out["altitude"] = data["alt"]
        if "temp" in data:
            out["temperature"] = data["temp"]
        if "heading" in data:
            out["course"] = data["heading"]
        if "batt" in data:
            out["battery"] = data["batt"]
        if "vel_v" in data:
            out["vspeed"] = data["vel_v"]
        if "vel_h" in data:
            out["speed"] = data["vel_h"]

        # Prefer auxiliary text, else use raw text
        if "aux" in data:
            out["message"] = data["aux"]
        elif "raw" in data:
            out["message"] = data["raw"]

        # Add communications frequency, if missing but known
        if "freq" in data:
            out["freq"] = data["freq"]
        elif self.frequency != 0:
            out["freq"] = self.frequency

        # Update location on the map
        if "lat" in out and "lon" in out and "id" in out:
            loc = SondeLocation(out)
            Map.getSharedInstance().updateLocation(out["id"], loc, out["mode"])

        # Report message
        ReportingEngine.getSharedInstance().spot(out)
        # Remove original data from the message
        if "data" in out:
            del out["data"]

        # Done
        return out
