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
        res["symbol"] = self.getSymbol()
        for key in ["comment", "course", "speed", "vspeed", "altitude", "weather", "device", "battery", "freq"]:
            if key in self.data:
                res[key] = self.data[key]
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
        for x in ["aprsid", "sats", "lat", "lon"]:
            if x in data:
                out[x] = data[x]

        # Convert some attributes
        if "id" in data:
            out["callsign"] = data["id"]
        if "alt" in data:
            out["altitude"] = data["alt"]
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
            out["comment"] = data["aux"]
        elif "raw" in data:
            out["comment"] = data["raw"]

        # Add device model
        device = ""
        if "rs41_mainboard" in data:
            device = data["rs41_mainboard"]
            if "rs41_mainboard_fw" in data:
                device += " " + data["rs41_mainboard_fw"]
        elif "type" in data:
            device = data["type"]
            if "subtype" in data:
                device += " " + data["subtype"]
        if len(device) > 0:
            out["device"] = device

        # Add weather
        weather = {}
        if "temp" in data:
            weather["temperature"] = data["temp"]
        if "pressure" in data:
            weather["pressure"] = data["pressure"]
        if "humidity" in data:
            weather["humidity"] = data["humidity"]
        if weather:
            out["weather"] = weather

        # Add communications frequency, if missing but known
        if "freq" in data:
            out["freq"] = data["freq"]
        elif self.frequency != 0:
            out["freq"] = self.frequency

        logger.debug("decoded radiosonde data: %s", out)

        # Update location on the map
        if "lat" in out and "lon" in out and "callsign" in out:
            loc = SondeLocation(out)
            Map.getSharedInstance().updateLocation(out["callsign"], loc, out["mode"])

        # Report message
        ReportingEngine.getSharedInstance().spot(out)
        # Remove original data from the message
        if "data" in out:
            del out["data"]

        # Done
        return out
