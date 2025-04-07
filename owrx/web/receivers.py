from owrx.web import WebAgent

import threading
import logging
import json
import re

logger = logging.getLogger(__name__)

class Receivers(WebAgent):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with Receivers.creationLock:
            if Receivers.sharedInstance is None:
                Receivers.sharedInstance = Receivers("receivers.json")
        return Receivers.sharedInstance

    @staticmethod
    def start():
        Receivers.getSharedInstance().startThread()

    @staticmethod
    def stop():
        Receivers.getSharedInstance().stopThread()

    def __init__(self, dataName: str):
        super().__init__(dataName)

    def _loadFromWeb(self):
        # Cached receivers database stale, update it
        receivers = {}
        logger.info("Scraping KiwiSDR website...")
        receivers.update(self.scrapeKiwiSDR())
        logger.info("Scraping WebSDR website...")
        receivers.update(self.scrapeWebSDR())
        logger.info("Scraping OpenWebRX website...")
        receivers.update(self.scrapeOWRX())
        return list(receivers.values()) if len(receivers) > 0 else None

    #
    # Following functions scrape data from websites
    #

    def scrapeOWRX(self, url: str = "https://www.receiverbook.de/map"):
        patternJson = re.compile(r"^\s*var\s+receivers\s+=\s+(\[.*\]);\s*$")
        result = {}
        try:
            data = None
            for line in self._openUrl(url).readlines():
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
                        id = re.sub(r"^.*://(.*?)(/.*)?$", r"\1", r["url"])
                        if "version" in r:
                            dev = r["type"] + " " + r["version"]
                        else:
                            dev = r["type"]
                        result[id] = {
                            "type"    : "latlon",
                            "mode"    : r["type"],
                            "id"      : id,
                            "lat"     : lat,
                            "lon"     : lon,
                            "comment" : r["label"],
                            "url"     : r["url"],
                            "device"  : dev
                        }
                        # Offset colocated receivers by ~500m
                        lon = lon + 0.0005

        except Exception as e:
            logger.error("scrapeOWRX() exception: {0}".format(e))

        # Done
        return result

    def scrapeWebSDR(self, url: str = "http://websdr.ewi.utwente.nl/~~websdrlistk?v=1&fmt=2&chseq=0"):
        result = {}
        try:
            data = self._openUrl(url).read().decode('utf-8')
            data = json.loads(re.sub(r"^\s*//.*", "", data, flags=re.MULTILINE))

            for entry in data:
                if "lat" in entry and "lon" in entry and "url" in entry:
                    # Save accumulated attributes, use hostname as key
                    id  = re.sub(r"^.*://(.*?)(/.*)?$", r"\1", entry["url"])
                    lat = entry["lat"]
                    lon = entry["lon"]
                    result[id] = {
                        "type"    : "latlon",
                        "mode"    : "WebSDR",
                        "id"      : id,
                        "lat"     : lat,
                        "lon"     : lon,
                        "comment" : entry["desc"],
                        "url"     : entry["url"],
                        "users"   : int(entry["users"]),
                        "device"  : "WebSDR"
                    }

        except Exception as e:
            logger.error("scrapeWebSDR() exception: {0}".format(e))

        # Done
        return result

    def scrapeKiwiSDR(self, url: str = "http://kiwisdr.com/public/"):
        result = {}
        try:
            patternAttr = re.compile(r".*<!--\s+(\S+)=(.*)\s+-->.*")
            patternUrl  = re.compile(r".*<a\s+href=['\"](\S+?)['\"].*>.*</a>.*")
            patternGps  = re.compile(r"\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)")
            entry = {}

            for line in self._openUrl(url).readlines():
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
                            id  = re.sub(r"^.*://(.*?)(/.*)?$", r"\1", entry["url"])
                            lat = float(m.group(1))
                            lon = float(m.group(2))
                            result[id] = {
                                "type"    : "latlon",
                                "mode"    : "KiwiSDR",
                                "id"      : id,
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
                            }
                    # Clear current entry
                    entry = {}
                else:
                    # Save all parsed attributes in the current entry
                    m = patternAttr.match(line)
                    if m is not None:
                        # Save attribute in the current entry
                        entry[m.group(1).lower()] = m.group(2)

        except Exception as e:
            logger.error("scrapeKiwiSDR() exception: {0}".format(e))

        # Done
        return result
