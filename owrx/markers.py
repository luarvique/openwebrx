from owrx.config.core import CoreConfig
from owrx.map import Map, Location
from owrx.aprs import getSymbolData
from json import JSONEncoder
from owrx.eibi import EIBI_Locations

import urllib
import threading
import logging
import json
import re
import os
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MyJSONEncoder(JSONEncoder):
    def default(self, obj):
        return obj.toJSON()


class MarkerLocation(Location):
    def __init__(self, attrs):
        self.attrs = attrs

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
    def _getCachedMarkersFile():
        coreConfig = CoreConfig()
        return "{data_directory}/markers.json".format(data_directory=coreConfig.get_data_directory())

    def __init__(self):
        self.markers = {}
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

    def toJSON(self):
        return self.markers

    def refresh(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._refreshThread)
            self.thread.start()

    def _refreshThread(self):
        logger.debug("Starting marker database refresh...")

        # No markers yet
        self.markers = {}

        # This file contains cached database
        file = self._getCachedMarkersFile()
        ts   = os.path.getmtime(file) if os.path.isfile(file) else 0

        # Try loading cached database from file first, unless stale
        if time.time() - ts < 60*60*24:
            logger.debug("Loading cached markers from '{0}'...".format(file))
            self.markers.update(self.loadMarkers(file))
        else:
            # Scrape websites for data
            cache = {}
            logger.debug("Scraping KiwiSDR web site...")
            cache.update(self.scrapeKiwiSDR())
            logger.debug("Scraping WebSDR web site...")
            cache.update(self.scrapeWebSDR())
            logger.debug("Scraping OpenWebRX web site...")
            cache.update(self.scrapeOWRX())
            # Save parsed data into a file
            logger.debug("Saving {0} markers to '{1}'...".format(len(self.markers), file))
            try:
                with open(file, "w") as f:
                    json.dump(cache, f, cls=MyJSONEncoder, indent=2)
                    f.close()
            except Exception as e:
                logger.debug("Exception: {0}".format(e))
            # Add scraped data to the database
            self.markers.update(cache)

        # Load markers from the EIBI database
        logger.debug("Loading EIBI transmitter locations...")
        self.markers.update(self.loadEIBI())

        # Load markers from local files
        for file in self.fileList:
            if os.path.isfile(file):
                logger.debug("Loading markers from '{0}'...".format(file))
                self.markers.update(self.loadMarkers(file))

        # Update map with markers
        logger.debug("Updating map...")
        self.updateMap()

        # Done
        logger.debug("Done refreshing marker database.")
        self.thread = None

    def loadMarkers(self, fileName: str):
        # Load markers list from JSON file
        try:
            with open(fileName, "r") as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            logger.debug("loadMarkers() exception: {0}".format(e))
            return

        # Process markers list
        result = {}
        for key in db.keys():
            attrs = db[key]
            result[key] = MarkerLocation(attrs)

        # Done
        return result

    def loadEIBI(self):
        #url = "https://www.short-wave.info/index.php?txsite="
        url = "https://www.google.com/search?q="
        result = {}
        # Load transmitter sites from EIBI database
        for entry in EIBI_Locations:
            rl = MarkerLocation({
                "type"    : "feature",
                "mode"    : "Stations",
                "comment" : "Transmitter",
                "id"      : entry["name"],
                "lat"     : entry["lat"],
                "lon"     : entry["lon"],
                "url"     : url + urllib.parse.quote_plus(entry["name"])
            })
            result[rl.getId()] = rl
        # Done
        return result

    def updateMap(self):
        for r in self.markers.values():
            Map.getSharedInstance().updateLocation(r.getId(), r, r.getMode(), permanent=True)

    def scrapeOWRX(self, url: str = "https://www.receiverbook.de/map"):
        patternJson = re.compile(r"^\s*var\s+receivers\s+=\s+(\[.*\]);\s*$")
        result = {}
        try:
            data = None
            for line in urllib.request.urlopen(url).readlines():
                # Convert read bytes to a string
                line = line.decode('utf-8')
                # When we encounter a URL...
                m = patternJson.match(line)
                if m:
                    data = json.loads(m.group(1))
                    break
            if data is not None:
                for entry in data:
                    lat = entry["location"]["coordinates"][1]
                    lon = entry["location"]["coordinates"][0]
                    for r in entry["receivers"]:
                        if "version" in r:
                            dev = r["type"] + " " + r["version"]
                        else:
                            dev = r["type"]
                        rl = MarkerLocation({
                            "type"    : "feature",
                            "mode"    : r["type"],
                            "id"      : re.sub(r"^.*://(.*?)(/.*)?$", r"\1", r["url"]),
                            "lat"     : lat,
                            "lon"     : lon,
                            "comment" : r["label"],
                            "url"     : r["url"],
                            "device"  : dev
                        })
                        result[rl.getId()] = rl
                        # Offset colocated receivers by ~500m
                        lon = lon + 0.0005

        except Exception as e:
            logger.debug("scrapeOWRX() exception: {0}".format(e))

        # Done
        return result

    def scrapeWebSDR(self, url: str = "http://websdr.ewi.utwente.nl/~~websdrlistk?v=1&fmt=2&chseq=0"):
        result = {}
        try:
            data = urllib.request.urlopen(url).read().decode('utf-8')
            data = json.loads(re.sub("^\s*//.*", "", data, flags=re.MULTILINE))

            for entry in data:
                if "lat" in entry and "lon" in entry and "url" in entry:
                    # Save accumulated attributes, use hostname as key
                    lat = entry["lat"]
                    lon = entry["lon"]
                    rl  = MarkerLocation({
                        "type"    : "feature",
                        "mode"    : "WebSDR",
                        "id"      : re.sub(r"^.*://(.*?)(/.*)?$", r"\1", entry["url"]),
                        "lat"     : lat,
                        "lon"     : lon,
                        "comment" : entry["desc"],
                        "url"     : entry["url"],
                        "users"   : int(entry["users"]),
                        "device"  : "WebSDR"
                    })
                    result[rl.getId()] = rl

        except Exception as e:
            logger.debug("scrapeWebSDR() exception: {0}".format(e))

        # Done
        return result

    def scrapeKiwiSDR(self, url: str = "http://kiwisdr.com/public/"):
        result = {}
        try:
            patternAttr = re.compile(r".*<!--\s+(\S+)=(.*)\s+-->.*")
            patternUrl  = re.compile(r".*<a\s+href=['\"](\S+?)['\"].*>.*</a>.*")
            patternGps  = re.compile(r"\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)")
            entry = {}

            for line in urllib.request.urlopen(url).readlines():
                # Convert read bytes to a string
                line = line.decode('utf-8')
                # When we encounter a URL...
                m = patternUrl.match(line)
                if m is not None:
                    # Add URL attribute
                    entry["url"] = m.group(1)
                    # Must have "gps" attribut with latitude / longitude
                    if "gps" in entry and "url" in entry:
                        m = patternGps.match(entry["gps"])
                        if m is not None:
                            # Save accumulated attributes, use hostname as key
                            lat = float(m.group(1))
                            lon = float(m.group(2))
                            rl = MarkerLocation({
                                "type"    : "feature",
                                "mode"    : "KiwiSDR",
                                "id"      : re.sub(r"^.*://(.*?)(/.*)?$", r"\1", entry["url"]),
                                "lat"     : lat,
                                "lon"     : lon,
                                "comment" : entry["name"],
                                "url"     : entry["url"],
                                "users"   : int(entry["users"]),
                                "maxusers": int(entry["users_max"]),
                                "loc"     : entry["loc"],
                                "altitude": int(entry["asl"]),
                                "antenna" : entry["antenna"],
                                "device"  : re.sub("_v", " ", entry["sw_version"])
                            })
                            result[rl.getId()] = rl
                    # Clear current entry
                    entry = {}
                else:
                    # Save all parsed attributes in the current entry
                    m = patternAttr.match(line)
                    if m is not None:
                        # Save attribute in the current entry
                        entry[m.group(1).lower()] = m.group(2)

        except Exception as e:
            logger.debug("scrapeKiwiSDR() exception: {0}".format(e))

        # Done
        return result