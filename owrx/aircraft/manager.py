from owrx.map import Map, LatLngLocation
from owrx.color import ColorCache
from owrx.config import Config
from datetime import datetime

import threading
import math
import time

import logging

logger = logging.getLogger(__name__)


#
# Aircraft categories
#
ADSB_CATEGORIES = {
  "A0": (0, 0),  # No ADS-B emitter category information
  "A1": (3, 0),  # Light (< 15500 lbs)
  "A2": (7, 6),  # Small (15500 to 75000 lbs)
  "A3": (5, 0),  # Large (75000 to 300000 lbs)
  "A4": (4, 0),  # High vortex large (aircraft such as B-757)
  "A5": (1, 7),  # Heavy (> 300000 lbs)
  "A6": (7, 0),  # High performance (> 5g acceleration and 400 kts)
  "A7": (6, 5),  # Rotorcraft, regardless of weight
  "B0": (0, 0),  # No ADS-B emitter category information
  "B1": (1, 6),  # Glider or sailplane, regardless of weight
  "B2": (2, 0),  # Airship or balloon, regardless of weight
  "B3": (10, 0), # Parachutist / skydiver
  "B4": (10, 0), # Ultralight / hang-glider / paraglider
  "B5": (0, 0),  # Reserved
  "B6": (4, 3),  # Unmanned aerial vehicle, regardless of weight
  "B7": (4, 5),  # Space / trans-atmospheric vehicle
  "C0": (4, 8),  # No ADS-B emitter category information
  "C1": (2, 8),  # Surface vehicle – emergency vehicle
  "C2": (3, 8),  # Surface vehicle – service vehicle
  "C3": (5, 8),  # Point obstacle (includes tethered balloons)
  "C4": (6, 9),  # Cluster obstacle
  "C5": (2, 8),  # Line obstacle
  "C6": (2, 8),  # Reserved
  "C7": (2, 8),  # Reserved
}

MODE_CATEGORIES = {
  "ADSB":  (0, 0),
  "ACARS": (5, 10),
  "HFDL":  (6, 10),
  "VDL2":  (7, 10),
  "UAT":   (0, 0)
}


#
# This class represents current aircraft location compatible with
# the APRS markers. It can be used for displaying aircraft on the
# map.
#
class AircraftLocation(LatLngLocation):
    def __init__(self, data):
        super().__init__(data["lat"], data["lon"])
        # Complete aircraft data
        self.data = data

    def getSymbol(self):
        # Add an aircraft symbol
        if "category" in self.data and self.data["category"] in ADSB_CATEGORIES:
            # Add symbol by aircraft category
            cat = ADSB_CATEGORIES[self.data["category"]]
            return { "x": cat[0], "y": cat[1] }
        elif "mode" in self.data and self.data["mode"] in MODE_CATEGORIES:
            # Add symbol by comms moce (red, green, or blue)
            cat = MODE_CATEGORIES[self.data["mode"]]
            return { "x": cat[0], "y": cat[1] }
        else:
            # Default to white symbols
            return { "x": 0, "y": 0 }

    def __dict__(self):
        res = super(AircraftLocation, self).__dict__()
        res["symbol"] = self.getSymbol()
        # Convert aircraft-specific data into APRS-like data
        for x in ["icao", "aircraft", "flight", "country", "ccode", "speed", "altitude", "course", "destination", "origin", "vspeed", "squawk", "rssi", "msglog", "ttl", "temperature", "wind", "route"]:
            if x in self.data:
                res[x] = self.data[x]
        # Return APRS-like dictionary object
        return res


#
# A global object of this class collects information on all
# currently reporting aircraft.
#
class AircraftManager(object):
    sharedInstance = None
    creationLock = threading.Lock()

    # Return a global instance of the aircraft manager.
    @staticmethod
    def getSharedInstance():
        with AircraftManager.creationLock:
            if AircraftManager.sharedInstance is None:
                AircraftManager.sharedInstance = AircraftManager()
        return AircraftManager.sharedInstance

    # Get unique aircraft ID, in flight -> tail -> ICAO ID order.
    @staticmethod
    def getAircraftId(data):
        if "icao" in data:
            return data["icao"]
        elif "aircraft" in data:
            return data["aircraft"]
        elif "flight" in data:
            return data["flight"]
        else:
            return None

    # Compute bearing (in degrees) between two latlons.
    @staticmethod
    def bearing(p1, p2):
        d   = (p2[1] - p1[1]) * math.pi / 180
        pr1 = p1[0] * math.pi / 180
        pr2 = p2[0] * math.pi / 180
        y   = math.sin(d) * math.cos(pr2)
        x   = math.cos(pr1) * math.sin(pr2) - math.sin(pr1) * math.cos(pr2) * math.cos(d)
        return (math.atan2(y, x) * 180 / math.pi + 360) % 360

    def __init__(self):
        self.lock = threading.Lock()
        self.cleanupPeriod = 60
        self.maxMsgLog = 20
        self.colors = ColorCache()
        self.aircraft = {}
        # Start periodic cleanup task
        self.thread = threading.Thread(target=self._cleanupThread, name=type(self).__name__ + ".Cleanup")
        self.thread.start()

    # Perform periodic cleanup
    def _cleanupThread(self):
        while self.thread is not None:
            time.sleep(self.cleanupPeriod)
            self.cleanup()

    # Get aircraft data by ID.
    def getAircraft(self, id):
        return self.aircraft[id] if id in self.aircraft else {}

    # Add a new aircraft to the database, or update existing aircraft data.
    def update(self, data):
        # Not updated yet
        updated = False

        # Identify aircraft the best we can, it MUST have some ID
        id = self.getAircraftId(data)
        if not id:
            return updated

        # Add timestamp, if missing
        if "timestamp" not in data:
            data["timestamp"] = round(datetime.now().timestamp() * 1000)

        # Add time-to-live
        pm = Config.get()
        mode = data["mode"]
        if mode == "ACARS":
            data["ttl"] = data["timestamp"] + pm["acars_ttl"] * 1000
        elif mode == "VDL2":
            data["ttl"] = data["timestamp"] + pm["vdl2_ttl"] * 1000
        elif mode == "HFDL":
            data["ttl"] = data["timestamp"] + pm["hfdl_ttl"] * 1000
        else:
            # Assume ADSB/UAT time-to-live
            data["ttl"] = data["timestamp"] + pm["adsb_ttl"] * 1000

        # Now operating on the database...
        with self.lock:
            # Merge database entries in flight -> tail -> ICAO ID order
            if "icao" in data:
                if "flight" in data:
                    self._merge(data["icao"], data["flight"])
                if "aircraft" in data:
                    self._merge(data["icao"], data["aircraft"])
            elif "aircraft" in data and "flight" in data:
                self._merge(data["aircraft"], data["flight"])

            # If no such ID yet...
            if id not in self.aircraft:
                logger.info("Adding %s" % id)
                # Create a new record
                item = self.aircraft[id] = data.copy()
                updated = True
            else:
                # Use existing record
                item = self.aircraft[id]
                # If we have got newer data...
                if data["timestamp"] > item["timestamp"]:
                    # Get previous and current positions
                    pos0 = (item["lat"], item["lon"]) if "lat" in item and "lon" in item else None
                    pos1 = (data["lat"], data["lon"]) if "lat" in data and "lon" in data else None
                    # Update existing record
                    item.update(data)
                    updated = True
                    # If both current and previous positions exist, compute course
                    if "course" not in data and pos0 and pos1 and pos1 != pos0:
                        item["course"] = data["course"] = round(self.bearing(pos0, pos1))
                        #logger.debug("Updated %s course to %d degrees" % (id, item["course"]))

            # Only if we have applied this update...
            if updated:
                # Add incoming messages to the log
                if "message" in data:
                    if "msglog" not in item:
                        item["msglog"] = [ data["message"] ]
                    else:
                        msglog = item["msglog"]
                        msglog.append(data["message"])
                        if len(msglog) > self.maxMsgLog:
                            item["msglog"] = item["msglog"][-self.maxMsgLog:]
                # Update aircraft on the map
                if "lat" in item and "lon" in item and "mode" in item:
                    loc = AircraftLocation(item)
                    Map.getSharedInstance().updateLocation(id, loc, item["mode"])
                    # Can later use this for linking to the map
                    data["mapid"] = id

            # Update input data with computed data
            for key in ["icao", "aircraft", "flight"]:
                if key in item:
                    data[key] = item[key]

        # Assign input data a color by its updated aircraft ID
        data["color"] = self.colors.getColor(self.getAircraftId(data))

        # Return TRUE if updated database
        return updated

    # Remove all database entries older than given time.
    def cleanup(self):
        now = datetime.now().timestamp() * 1000
        # Now operating on the database...
        with self.lock:
            too_old = [x for x in self.aircraft.keys() if self.aircraft[x]["ttl"] < now]
            if too_old:
                logger.info("Following aircraft have become stale: {0}".format(too_old))
                for id in too_old:
                    self._removeFromMap(id)
                    del self.aircraft[id]

    # Get current aircraft data reported in given mode
    def getData(self, mode: str = None):
        result = []
        with self.lock:
            for id in self.aircraft.keys():
                item = self.aircraft[id]
                # Ignore duplicates and data reported in different modes
                if id == self.getAircraftId(item):
                    if not mode or mode == item["mode"]:
                        result.append(item)
        return result

    # Internal function to merge aircraft data
    def _merge(self, id1, id2):
        if id1 not in self.aircraft:
            if id2 in self.aircraft:
                logger.info("Linking %s to %s" % (id1, id2))
                self.aircraft[id1] = self.aircraft[id2]
        elif id2 not in self.aircraft:
            logger.info("Linking %s to %s" % (id2, id1))
            self.aircraft[id2] = self.aircraft[id1]
        else:
            item1 = self.aircraft[id1]
            item2 = self.aircraft[id2]
            if item1 is not item2:
                # Make sure ID1 is always newer than ID2
                if item1["timestamp"] < item2["timestamp"]:
                    item1, item2 = item2, item1
                    id1,   id2   = id2,   id1
                # Update older data with newer data
                logger.info("Merging %s into %s" % (id2, id1))
                item2.update(item1)
                self.aircraft[id1] = item2
                # Change ID2 color to ID1
                self.colors.rename(id2, id1)
                # Remove ID2 airplane from the map
                self._removeFromMap(id2)

    # Internal function to remove aircraft from the map
    def _removeFromMap(self, id):
        # Ignore errors removing non-existing flights
        try:
            item = self.aircraft[id]
            if "lat" in item and "lon" in item:
                Map.getSharedInstance().removeLocation(id)
        except Exception as exptn:
            logger.error("Exception removing aircraft %s: %s" % (id, str(exptn)))
