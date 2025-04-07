from owrx.config import Config
from owrx.bookmarks import Bookmark
from owrx.web import WebAgent
from owrx.version import openwebrx_version

import urllib
import threading
import logging
import json
import os
import math

logger = logging.getLogger(__name__)

#
# Maximal distance a repeater can reach (kilometers)
#
MAX_DISTANCE = 200

class Repeaters(WebAgent):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with Repeaters.creationLock:
            if Repeaters.sharedInstance is None:
                Repeaters.sharedInstance = Repeaters("repeaters.json")
        return Repeaters.sharedInstance

    @staticmethod
    def start():
        Repeaters.getSharedInstance().startThread()

    @staticmethod
    def stop():
        Repeaters.getSharedInstance().stopThread()

    # Compute distance, in kilometers, between two latlons.
    @staticmethod
    def distKm(p1, p2):
        # Earth radius in km
        earthR = 6371
        # Convert degrees to radians
        rlat1 = p1[0] * (math.pi/180)
        rlat2 = p2[0] * (math.pi/180)
        # Compute difference in radians
        difflat = rlat2 - rlat1
        difflon = (p2[1] - p1[1]) * (math.pi/180)
        # Compute distance
        return round(2 * earthR * math.asin(math.sqrt(
            math.sin(difflat/2) * math.sin(difflat/2) +
            math.cos(rlat1) * math.cos(rlat2) * math.sin(difflon/2) * math.sin(difflon/2)
        )))

    # Guess main operating mode, prefer free modes
    @staticmethod
    def getModulation(entry):
        if "FM Analog" in entry and entry["FM Analog"]=="Yes":
            return "nfm"
        elif "M17" in entry and entry["M17"]=="Yes":
            return "m17"
        elif "DMR" in entry and entry["DMR"]=="Yes":
            return "dmr"
        elif "D-Star" in entry and entry["D-Star"]=="Yes":
            return "dstar"
        elif "System Fusion" in entry and entry["System Fusion"]=="Yes":
            return "ysf"
        elif "NXDN" in entry and entry["NXDN"]=="Yes":
            return "nxdn"
        else:
            return "nfm"

    # Compose textual description of an entry
    @staticmethod
    def getDescription(entry):
        description = []
        # Add information from the entry to the description
        if "status" in entry:
            pm = Config.get()
            rxPos = (pm["receiver_gps"]["lat"], pm["receiver_gps"]["lon"])
            description += ["{0}, {1}km away.".format(
                entry["status"],
                Repeaters.distKm(rxPos, (entry["lat"], entry["lon"]))
            )]
        if "updated" in entry:
            description += ["Last updated " + entry["updated"] + "."]
        if "comment" in entry:
            description += [entry["comment"]]
        # Done
        return " ".join(description)

    def __init__(self, dataName: str):
        super().__init__(dataName)
        # Update repeater list when receiver location changes
        pm = Config.get()
        self.location = (pm["receiver_gps"]["lat"], pm["receiver_gps"]["lon"])
        pm.wireProperty("receiver_gps", self._updateLocation)

    # Delete current repeater list when receiver location changes.
    def _updateLocation(self, location):
        location = (location["lat"], location["lon"])
        file = self._getCachedDatabaseFile()
        dist = self.distKm(location, self.location)
        if not os.path.exists(file):
            # If there are no repeaters loaded, just keep new location
            self.location = location
        elif dist > 10:
            # Do not delete repeater list unless receiver moved a lot
            logger.info("Receiver moved by {0}km, deleting '{1}'...".format(dist, file))
            self.location = location
            os.remove(file)

    #
    # Load repeater database from the RepeaterBook.com website.
    #
    def _loadFromWeb(self):
        return self.loadFromWeb("https://www.repeaterbook.com/api/{script}?qtype=prox&dunit=km&lat={lat}&lng={lon}&dist={range}", MAX_DISTANCE)

    def loadFromWeb(self, url: str, rangeKm: int):
        result = []
        try:
            pm   = Config.get()
            lat  = pm["receiver_gps"]["lat"]
            lon  = pm["receiver_gps"]["lon"]
            hdrs = { "User-Agent": "(OpenWebRX+ " + openwebrx_version + ", luarvique@gmail.com)" }
            # Start with US/Canada database for north-wester quartersphere
            if lat > 0 and lon < 0:
                scps = ["export.php", "exportROW.php"]
            else:
                scps = ["exportROW.php", "export.php"]
            # Try scripts in order...
            for s in scps:
                url1 = url.format(script = s, lat = lat, lon = lon, range = rangeKm)
                req  = urllib.request.Request(url1, headers = hdrs)
                data = urllib.request.urlopen(req).read().decode("utf-8")
                logger.info("Trying {0} ... got {1} bytes".format(url1, len(data)))
                data = json.loads(data)
                # ...until we get the result
                if "results" in data and len(data["results"]) > 0:
                    break
            # If no results, do not continue
            if "results" not in data:
                return None
            # For every entry in the response...
            for entry in data["results"]:
                result += [{
                    "name"    : entry["Callsign"],
                    "lat"     : float(entry["Lat"]),
                    "lon"     : float(entry["Long"]),
                    "freq"    : int(float(entry["Frequency"]) * 1000000),
                    "mode"    : self.getModulation(entry),
                    "status"  : entry["Operational Status"],
                    "updated" : entry["Last Update"],
                    "comment" : entry["Notes"]
                }]

        except Exception as e:
            logger.error("loadFromWeb() exception: {0}".format(e))
            return None

        # Done
        return result

    #
    # Get bookmarks for all repeaters that are within given
    # frequency and distance ranges.
    #
    def getBookmarks(self, frequencyRange, rangeKm: int = MAX_DISTANCE):
        # Make sure freq2>freq1
        (f1, f2) = frequencyRange
        if f1>f2:
            f = f1
            f1 = f2
            f2 = f

        # Get receiver location for computing distance
        pm = Config.get()
        rxPos = (pm["receiver_gps"]["lat"], pm["receiver_gps"]["lon"])

        # No result yet
        logger.info("Creating bookmarks for {0}-{1}kHz within {2}km...".format(f1//1000, f2//1000, rangeKm))
        result = {}

        # Search for repeaters within frequency and distance ranges
        with self.lock:
            for entry in self.data:
                try:
                    f = entry["freq"]
                    if f1 <= f <= f2:
                        d = self.distKm(rxPos, (entry["lat"], entry["lon"]))
                        if d <= rangeKm and (f not in result or d < result[f][1]):
                            result[f] = (entry, d)

                except Exception as e:
                    logger.error("getBookmarks() exception: {0}".format(e))

        # Return bookmarks for all found entries
        logger.info("Created {0} bookmarks for {1}-{2}kHz within {3}km.".format(len(result), f1//1000, f2//1000, rangeKm))
        return [ Bookmark({
            "name"        : result[f][0]["name"],
            "modulation"  : result[f][0]["mode"],
            "frequency"   : result[f][0]["freq"],
            "description" : Repeaters.getDescription(result[f][0])
        }, srcFile = "RepeaterBook") for f in result.keys() ]

    #
    # Get entries for all repeaters that are within given distance
    # range from the receiver.
    #
    def getAllInRange(self, rangeKm: int = MAX_DISTANCE):
        # Get receiver location for computing distance
        pm = Config.get()
        rxPos = (pm["receiver_gps"]["lat"], pm["receiver_gps"]["lon"])

        # No result yet
        logger.info("Looking for repeaters within {0}km...".format(rangeKm))
        result = []

        # Search for repeaters within given distance range
        with self.lock:
            for entry in self.data:
                try:
                    if self.distKm(rxPos, (entry["lat"], entry["lon"])) <= rangeKm:
                        result += [entry]

                except Exception as e:
                    logger.error("getAllInRange() exception: {0}".format(e))

        # Done
        logger.info("Found {0} repeaters within {1}km.".format(len(result), rangeKm))
        return result

