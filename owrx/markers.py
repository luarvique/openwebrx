from owrx.config.core import CoreConfig
from owrx.config import Config
from owrx.version import openwebrx_version
from owrx.map import Map, Location
from owrx.aprs import getSymbolData
from owrx.web.receivers import Receivers
from owrx.web.repeaters import Repeaters
from owrx.web.eibi import EIBI
from json import JSONEncoder
from datetime import datetime, timedelta, timezone

import urllib
import threading
import logging
import json
import re
import os

logger = logging.getLogger(__name__)


class MyJSONEncoder(JSONEncoder):
    def default(self, obj):
        return obj.toJSON()


class MarkerLocation(Location):
    def __init__(self, attrs):
        self.attrs = attrs
        # Making sure older cached files load
        self.attrs["type"] = "latlon"

    def getId(self):
        return self.attrs["id"]

    def getMode(self):
        return self.attrs["mode"]

    def __dict__(self):
        return self.attrs

    def toJSON(self):
        return self.attrs


class Markers(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with Markers.creationLock:
            if Markers.sharedInstance is None:
                Markers.sharedInstance = Markers()
        return Markers.sharedInstance

    @staticmethod
    def start():
        Markers.getSharedInstance().startThread()
        Receivers.start()
        Repeaters.start()
        EIBI.start()

    @staticmethod
    def stop():
        Markers.getSharedInstance().stopThread()
        Receivers.stop()
        Repeaters.stop()
        EIBI.stop()

    @staticmethod
    def _getCachedMarkersFile():
        coreConfig = CoreConfig()
        return "{data_directory}/markers.json".format(data_directory=coreConfig.get_data_directory())

    def __init__(self):
        self.event = threading.Event()
        self.fmarkers = {}
        self.wmarkers = {}
        self.smarkers = {}
        self.thread = None
        # Known database files
        self.fileList = [
            "markers.json",
            "/etc/openwebrx/markers.json",
        ]
        # Find additional marker files in the markers.d folder
        try:
            markersDir = "/etc/openwebrx/markers.d"
            self.fileList += [ markersDir + "/" + file
                for file in os.listdir(markersDir) if file.endswith(".json")
            ]
        except Exception:
            pass

    # Start the main thread
    def startThread(self):
        if self.thread is None:
            self.event.clear()
            self.thread = threading.Thread(target=self._refreshThread, name=type(self).__name__)
            self.thread.start()

    # Stop the main thread
    def stopThread(self):
        if self.thread is not None:
            logger.info("Stopping marker database thread.")
            self.event.set()
            self.thread.join()
            self.thread = None

    # This is the actual thread function
    def _refreshThread(self):
        logger.info("Starting marker database thread...")

        # No markers yet
        self.markers   = {} # Static miscellaneous markers
        self.rxmarkers = {} # Online SDR receivers
        self.txmarkers = {} # Current transmitters (EIBI)
        self.remarkers = {} # Current repeaters (RepeaterBook)

        # Load miscellaneous markers from local files
        for file in self.fileList:
            if os.path.isfile(file):
                self.markers.update(self.loadMarkers(file))

        # Load list of online SDR receivers
        self.rxmarkers = self.loadReceivers()

        # Load current schedule from the EIBI database
        self.txmarkers = self.loadCurrentTransmitters()

        # Load repeaters from the Repeaters database
        self.remarkers = self.loadRepeaters()

        # Update map with markers
        logger.info("Updating map...")
        self.updateMap(self.markers)
        self.updateMap(self.rxmarkers)
        self.updateMap(self.txmarkers)
        self.updateMap(self.remarkers)

        #
        # Main Loop
        #

        while not self.event.is_set():
            # Wait until the head of an hour
            self.event.wait((60 - datetime.utcnow().minute) * 60)
            # Check if we need to exit
            if self.event.is_set():
                break

            # Load new transmitters schedule from the EIBI
            data = self.loadCurrentTransmitters()
            if data is not None:
                logger.info("Refreshing transmitters schedule...")
                self.applyUpdate(self.txmarkers, data)

            # Update receivers data as necessary
            data = self.loadReceivers(onlyNew=True)
            if data is not None:
                logger.info("Refreshing receiver markers...")
                self.applyUpdate(self.rxmarkers, data)

            # Update repeaters data as necessary
            data = self.loadRepeaters(onlyNew=True)
            if data is not None:
                logger.info("Refreshing repeater markers...")
                self.applyUpdate(self.remarkers, data)

            # Check if we need to exit
            if self.event.is_set():
                break

        # Done with the thread
        logger.info("Stopped marker database thread.")
        self.thread = None

    # Load markers from a given file
    def loadMarkers(self, file: str):
        logger.info("Loading markers from '{0}'...".format(file))
        # Load markers list from JSON file
        try:
            with open(file, "r") as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            logger.error("loadMarkers() exception: {0}".format(e))
            return {}
        # Process markers list
        result = {}
        for key in db.keys():
            attrs = db[key]
            result[key] = MarkerLocation(attrs)
        # Done
        logger.info("Loaded {0} markers from '{1}'.".format(len(result), file))
        return result

    # Update given markers on the map
    def updateMap(self, markers):
        # Must have valid markers to update
        if markers is not None:
            # Create a timestamp far into the future, for permanent markers
            map = Map.getSharedInstance()
            permanent = datetime.now(timezone.utc) + timedelta(weeks=500)
            for r in markers.values():
                map.updateLocation(r.getId(), r, r.getMode(), timestamp=permanent)

    # Apply updates to a given set of markers
    def applyUpdate(self, data, update):
        # If no update, exit
        if update is None:
            return
        # Remove data that no longer exists
        map = Map.getSharedInstance()
        nodata = [x for x in data.keys() if x not in update]
        for key in nodata:
            map.removeLocation(key)
            del data[key]
        # Create a timestamp far into the future, for permanent markers
        permanent = datetime.now(timezone.utc) + timedelta(weeks=500)
        # Update data that may have changed
        for key in update.keys():
            r = update[key]
            map.updateLocation(r.getId(), r, r.getMode(), timestamp=permanent)
            data[key] = r

    # Returns known online SDR receivers. Will update receivers cache
    # by scraping online databases as necessary.
    def loadReceivers(self, onlyNew: bool = False):
        # Refresh / load receivers database, as needed
        if not Receivers.getSharedInstance().hasFreshData() and onlyNew:
            return None
        # No result yet
        result = {}
        # Create markers from the current receivers database
        logger.info("Refreshing receivers database...")
        for entry in Receivers.getSharedInstance().getAll():
            rl = MarkerLocation(entry)
            result[rl.getId()] = rl
        # Done
        logger.info("Loaded {0} receivers.".format(len(result)))
        return result

    # Returns repeaters inside given range. Will query online database
    # for updated list of repeaters and cache it as necessary.
    def loadRepeaters(self, rangeKm: int = 200, onlyNew: bool = False):
        # Refresh / load repeaters database, as needed
        if not Repeaters.getSharedInstance().hasFreshData() and onlyNew:
            return None
        # No result yet
        result = {}
        # Load repeater sites from the cached database
        logger.info("Refreshing repeaters database...")
        for entry in Repeaters.getSharedInstance().getAllInRange(rangeKm):
            rl = MarkerLocation({
                "type"    : "latlon",
                "mode"    : "Repeaters",
                "id"      : entry["name"],
                "lat"     : entry["lat"],
                "lon"     : entry["lon"],
                "freq"    : entry["freq"],
                "mmode"   : entry["mode"],
                "status"  : entry["status"],
                "updated" : entry["updated"],
                "comment" : entry["comment"]
            })
            result[rl.getId()] = rl
        # Done
        logger.info("Loaded {0} repeaters.".format(len(result)))
        return result

    # Returns currently broadcasting transmitters. Will load a new
    # schedule from EIBI website and cache it as necessary.
    def loadCurrentTransmitters(self):
        #url = "https://www.short-wave.info/index.php?txsite="
        url = "https://www.google.com/search?q="
        result = {}

        # Load transmitter sites from EIBI database
        for entry in EIBI.getSharedInstance().currentTransmitters().values():
            # Extract target regions and languages, removing duplicates
            schedule = entry["schedule"]
            langs   = {}
            targets = {}
            comment = ""
            langstr = ""
#            for row in schedule:
#                lang   = row["lang"]
#                target = row["tgt"]
#                if target and target not in targets:
#                    targets[target] = True
#                    comment += (", " if comment else " to ") + target
#                if lang and lang not in langs:
#                    langs[lang] = True
#                    langstr += (", " if langstr else "") + re.sub(r"(:|\s*\().*$", "", lang)

            # Compose comment
            comment = ("Transmitting" + comment) if comment else "Transmitter"
            comment = (comment + " (" + langstr + ")") if langstr else comment

            rl = MarkerLocation({
                "type"    : "latlon",
                "mode"    : "Stations",
                "comment" : comment,
                "id"      : entry["name"],
                "lat"     : entry["lat"],
                "lon"     : entry["lon"],
                "ttl"     : entry["ttl"] * 1000,
                "url"     : url + urllib.parse.quote_plus(entry["name"]),
                "schedule": schedule
            })
            result[rl.getId()] = rl

        # Done
        logger.info("Loaded {0} transmitters from EIBI.".format(len(result)))
        return result
