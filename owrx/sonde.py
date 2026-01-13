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

    def __dict__(self):
        res = super(SondeLocation, self).__dict__()
        for key in ["symbol", "comment", "course", "speed", "vspeed", "altitude", "weather", "device", "battery", "freq"]:
            if key in self.data:
                res[key] = self.data[key]
        return res


class SondeParser(TextParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="SONDE", service=service)

    def parse(self, msg: bytes):
        # Expect JSON data in text form
        try:
            data = json.loads(msg)
        except Exception:
            logger.debug("Discarding raw message: '%s'", msg.decode("utf-8"))
            return None

        # Ignore "datetime" field for now ("%04d-%02d-%02dT%02d:%02d:%06.3fZ")
        out = {
            "mode"      : "SONDE",
            "timestamp" : round(datetime.now().timestamp() * 1000),
            "symbol"    : getSymbolData("O", "/"),
            "data"      : data
        }

        # Copy main attributes
        for x in ["aprsid", "sats", "lat", "lon"]:
            if x in data:
                out[x] = data[x]

        # Convert some attributes
        if "id" in data:
            out["source"] = data["id"]
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
        if "aux" in data:
            out["comment"] = data["aux"]

        # Add device model
        device = ""
        if "rs41_mainboard" in data:
            device = data["rs41_mainboard"]
            if "rs41_mainboard_fw" in data:
                device += " FW v" + str(data["rs41_mainboard_fw"])
        elif "type" in data:
            device = data["type"]
            if "subtype" in data:
                if data["subtype"].startswith(device):
                    device = data["subtype"]
                elif data["subtype"] != device:
                    device += " " + data["subtype"]
        if len(device) > 0:
            out["device"] = device

        # Add weather
        weather = {}
        if "temp" in data:
            weather["temperature"] = data["temp"]
        if "pressure" in data:
            weather["barometricpressure"] = data["pressure"]
        if "humidity" in data:
            weather["humidity"] = data["humidity"]
        if weather:
            out["weather"] = weather

        # Add communications frequency, if missing but known
        if "freq" in data:
            out["freq"] = data["freq"]
        elif self.frequency != 0:
            out["freq"] = self.frequency

        logger.debug("Decoded data: %s", out)

        # Report message
        ReportingEngine.getSharedInstance().spot(out)

        # Remove original data from the message
        if "data" in out:
            del out["data"]

        # Update location on the map
        if "lat" in out and "lon" in out and "source" in out:
            loc = SondeLocation(out)
            Map.getSharedInstance().updateLocation(out["source"], loc, out["mode"])

        # Do not return anything when in service mode
        return None if self.service else out
