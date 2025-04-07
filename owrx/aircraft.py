from owrx.toolbox import TextParser
from owrx.color import ColorCache
from owrx.map import Map, LatLngLocation
from owrx.aprs import getSymbolData
from owrx.config import Config
from owrx.reporting import ReportingEngine
from owrx.icao import IcaoRegistration, IcaoCountry
from datetime import datetime, timedelta
import threading
import pickle
import json
import math
import time
import re
import os

import logging

logger = logging.getLogger(__name__)

#
# Mode-S message formats
#
MODE_S_FORMATS = [
    "Short ACAS", None, None, None,
    "Altitude", "IDENT Reply", None, None,
    None, None, None, "ADSB",
    None, None, None, None,
    "Long ACAS", "Extended ADSB", "Supplementary ADSB", "Exetended Military",
    "Comm-B Altitude", "Comm-B IDENT Reply", "Military", None,
    "Comm-D Message"
]

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
        for x in ["icao", "aircraft", "flight", "country", "ccode", "speed", "altitude", "course", "destination", "origin", "vspeed", "squawk", "rssi", "msglog", "ttl"]:
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
            # Assume ADSB time-to-live
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


#
# Base class for aircraft message parsers.
#
class AircraftParser(TextParser):
    def __init__(self, filePrefix: str = None, service: bool = False):
        self.reFlight = re.compile("^([0-9A-Z]{2}|[A-Z]{3})0*([0-9]+[A-Z]*)$")
        self.reDots   = re.compile (r"^\.*([^\.].*?)\.*$")
        self.reIATA   = re.compile("^..[0-9]+$")
        super().__init__(filePrefix=filePrefix, service=service)

    def parse(self, msg: bytes):
        # Parse incoming message via mode-specific function
        out = self.parseAircraft(msg)
        if out is not None:
            # Remove extra zeros from the flight ID
            if "flight" in out:
                out["flight"] = self.reFlight.sub("\\1\\2", out["flight"])
            # Remove leading and trailing dots from ACARS data
            for key in ["aircraft", "origin", "destination"]:
                if key in out:
                    out[key] = self.reDots.sub("\\1", out[key])
            # Add communications frequency, if known
            if self.frequency != 0:
                out["freq"] = self.frequency
            # Add timestamp, if missing
            if "timestamp" not in out:
                out["timestamp"] = round(datetime.now().timestamp() * 1000)
            # Report message
            ReportingEngine.getSharedInstance().spot(out)
            # Remove original data from the message
            if "data" in out:
                del out["data"]
            # Update aircraft database with the new data
            AircraftManager.getSharedInstance().update(out)
        # Do not return anything when in service mode
        return None if self.service else out

    # Mode-specific parse function
    def parseAircraft(self, msg: bytes):
        return None

    # Common function to parse ACARS subframes in HFDL/VDL2/etc
    def parseAcars(self, data, out):
        # Collect data
        out["type"] = "ACARS frame"
        aircraft = data["reg"].strip()
        message  = data["msg_text"].strip()
        flight   = data["flight"].strip() if "flight" in data else ""
        if len(aircraft)>0:
            out["aircraft"] = aircraft
        if len(message)>0:
            out["message"] = message
        if len(flight)>0:
            out["flight"] = flight
        # Done
        return out

    # Common function to get country and aircraft registration from ICAO ID
    def parseIcaoId(self, icao, out):
        # Convert hex ICAO ID to an integer, if required
        if isinstance(icao, str):
            icao = int(icao, 16)
        country  = IcaoCountry.find(icao)
        aircraft = IcaoRegistration.find(icao)
        if country and country[0]:
            out["country"] = country[0]
        if country and country[1]:
            out["ccode"] = country[1]
        if aircraft:
            out["aircraft"] = aircraft
        # Done
        return out


#
# Parser for HFDL messages coming from DumpHFDL in JSON format.
#
class HfdlParser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="HFDL", service=service)

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        # @@@ Only parse messages that have LDPU frames for now !!!
        if "lpdu" not in data["hfdl"]:
            return {}
        # Collect basic data first
        out = {
            "mode"      : "HFDL",
            "timestamp" : round(data["hfdl"]["t"]["sec"] * 1000 + data["hfdl"]["t"]["usec"] / 1000),
            "data"      : data
        }
        # Parse LPDU if present
        if "lpdu" in data["hfdl"]:
            self.parseLpdu(data["hfdl"]["lpdu"], out)
        # Parse SPDU if present
        if "spdu" in data["hfdl"]:
            self.parseSpdu(data["hfdl"]["spdu"], out)
        # Parse MPDU if present
        if "mpdu" in data["hfdl"]:
            self.parseMpdu(data["hfdl"]["mpdu"], out)
        # Done
        return out

    def parseSpdu(self, data, out):
        # Not parsing yet
        out["type"] = "SPDU frame"
        return out

    def parseMpdu(self, data, out):
        # Not parsing yet
        out["type"] = "MPDU frame"
        return out

    def parseLpdu(self, data, out):
        # Collect data
        out["type"] = data["type"]["name"]
        # Add aircraft info, if present, assign color right away
        if "ac_info" in data and "icao" in data["ac_info"]:
            # Get ICAO ID
            out["icao"] = data["ac_info"]["icao"].strip()
            # Get country and aircraft registration from ICAO ID
            self.parseIcaoId(out["icao"], out)

        # Source might be a ground station
        #if data["src"]["type"] == "Ground station":
        #    out["flight"] = "GS-%d" % data["src"]["id"]
        # Parse HFNPDU is present
        if "hfnpdu" in data:
            self.parseHfnpdu(data["hfnpdu"], out)
        # Done
        return out

    def parseHfnpdu(self, data, out):
        # Use flight ID as unique identifier
        flight = data["flight_id"].strip() if "flight_id" in data else ""
        if len(flight)>0:
            out["flight"] = flight
        # If we see ACARS message, parse it and drop out
        if "acars" in data:
            return self.parseAcars(data["acars"], out)
        # If message carries time, parse it
        if "utc_time" in data:
            msgtime = data["utc_time"]
        elif "time" in data:
            msgtime = data["time"]
        else:
            msgtime = None
        # Add reported message time, if present
        if msgtime:
            out["msgtime"] = "%02d:%02d:%02d" % (
                msgtime["hour"], msgtime["min"], msgtime["sec"]
            )
        # Add aircraft location, if present
        if "pos" in data:
            out["lat"] = data["pos"]["lat"]
            out["lon"] = data["pos"]["lon"]
        # Done
        return out


#
# Parser for VDL2 messages coming from DumpVDL2 in JSON format.
#
class Vdl2Parser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="VDL2", service=service)

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        # Collect basic data first
        out = {
            "mode"      : "VDL2",
            "timestamp" : round(data["vdl2"]["t"]["sec"] * 1000 + data["vdl2"]["t"]["usec"] / 1000),
            "data"      : data
        }
        # Parse AVLC if present
        if "avlc" in data["vdl2"]:
            self.parseAvlc(data["vdl2"]["avlc"], out)
        # Done
        return out

    def parseAvlc(self, data, out):
        # Find if aircraft is message's source or destination
        if data["src"]["type"] == "Aircraft":
            p = data["src"]
        elif data["dst"]["type"] == "Aircraft":
            p = data["dst"]
        else:
            return out
        # Address is the ICAO ID
        out["icao"] = p["addr"]
        # Get country and aircraft registration from ICAO ID
        self.parseIcaoId(out["icao"], out)
        # Clarify message type as much as possible
        if "status" in p:
            out["type"] = p["status"]
        if "cmd" in data:
            if "type" in out:
                out["type"] += ", " + data["cmd"]
            else:
                out["type"] = data["cmd"]
        # Parse ACARS if present
        if "acars" in data:
            self.parseAcars(data["acars"], out)
        # Parse XID if present
        if "xid" in data:
            self.parseXid(data["xid"], out)
        # Done
        return out

    def parseXid(self, data, out):
        # Collect data
        out["type"] = "XID " + data["type_descr"]
        if "vdl_params" in data:
            # Parse VDL parameters array
            for p in data["vdl_params"]:
                if p["name"] == "ac_location":
                    # Parse location
                    out["lat"] = p["value"]["loc"]["lat"]
                    out["lon"] = p["value"]["loc"]["lon"]
                    # Ignore dummy altitude value
                    alt = p["value"]["alt"]
                    if alt < 192000:
                        out["altitude"] = round(alt)
                elif p["name"] == "dst_airport":
                    # Parse destination airport
                    out["destination"] = p["value"]
                elif p["name"] == "modulation_support":
                    # Parse supported modulations
                    out["modes"] = p["value"]
        # Done
        return out


#
# Parser for ADSB messages coming from Dump1090 in hexadecimal format.
#
class AdsbParser(AircraftParser):
    def __init__(self, service: bool = False, jsonFile: str = "/tmp/dump1090/aircraft.json"):
        super().__init__(filePrefix=None, service=service)
        self.jsonFile = jsonFile
        self.checkPeriod = 1
        self.lastParse = 0
        # Start periodic JSON file check
        self.thread = threading.Thread(target=self._refreshThread, name=type(self).__name__ + ".Refresh")
        self.thread.start()

    # Not parsing STDOUT
    def parseAircraft(self, msg: bytes):
        return None

    # Periodically check if Dump1090's JSON file has changed
    # and parse it if it has.
    def _refreshThread(self):
        lastUpdate = 0
        while self.thread is not None:
            # Wait until the next check
            time.sleep(self.checkPeriod)
            try:
                # If JSON file has updated since the last update, parse it
                ts = os.path.getmtime(self.jsonFile)
                if ts > lastUpdate:
                    lastUpdate = ts
                    parsed = self.parseJson(self.jsonFile)
                    if not self.service and parsed > 0:
                        data = AircraftManager.getSharedInstance().getData("ADSB")
                        self.writer.write(pickle.dumps({
                            "mode"     : "ADSB-LIST",
                            "aircraft" : data
                        }))
            except Exception as exptn:
                logger.info("Failed to check file '{0}': {1}".format(self.jsonFile, exptn))

    # Parse supplied JSON file in Dump1090 format.
    def parseJson(self, file: str):
        # Load JSON from supplied file
        try:
            with open(file, "r") as f:
                data = f.read()
                f.close()
                data = json.loads(data)
        except:
            return 0

        # Make sure we have the aircraft data
        if "aircraft" not in data or "now" not in data:
            return 0

        # This is our current timestamp
        now = data["now"]

        # Iterate over aircraft
        for entry in data["aircraft"]:
            # Do not update twice
            ts = now - entry["seen"]
            if ts <= self.lastParse:
                continue

            # Always present ADSB data
            out = {
                "mode"      : "ADSB",
                "icao"      : entry["hex"].upper(),
                "timestamp" : round(ts * 1000),
                "msgs"      : entry["messages"],
                "rssi"      : entry["rssi"]
            }

            # Country and aircraft registration from ICAO ID
            self.parseIcaoId(entry["hex"], out)

            # Position
            if "lat" in entry and "lon" in entry:
                out["lat"] = entry["lat"]
                out["lon"] = entry["lon"]

            # Flight identification, aircraft type, squawk code
            if "flight" in entry:
                out["flight"] = entry["flight"].strip()
            if "category" in entry:
                out["category"] = entry["category"]
            if "squawk" in entry:
                out["squawk"] = entry["squawk"]
            if "emergency" in entry and entry["emergency"] != "none":
                out["emergency"] = entry["emergency"].upper()

            # Altitude
            if "alt_geom" in entry:
                out["altitude"] = entry["alt_geom"]
            elif "alt_baro" in entry:
                out["altitude"] = entry["alt_baro"]

            # Round altitude
            if "altitude" in out:
                out["altitude"] = 0 if out["altitude"] == "ground" else round(out["altitude"])

            # Climb/descent rate
            if "geom_rate" in entry:
                out["vspeed"] = round(entry["geom_rate"])
            elif "baro_rate" in entry:
                out["vspeed"] = round(entry["baro_rate"])

            # Speed
            if "gs" in entry:
                out["speed"] = round(entry["gs"])
            elif "tas" in entry:
                out["speed"] = round(entry["tas"])
            elif "ias" in entry:
                out["speed"] = round(entry["ias"])

            # Heading
            if "true_heading" in entry:
                out["course"] = round(entry["true_heading"])
            elif "mag_heading" in entry:
                out["course"] = round(entry["mag_heading"])
            elif "track" in entry:
                out["course"] = round(entry["track"])

            # Outside temperature
            if "oat" in entry:
                out["temperature"] = entry["oat"]
            elif "tat" in entry:
                out["temperature"] = entry["tat"]

            # Update aircraft database with the new data
            AircraftManager.getSharedInstance().update(out)

        # Save last parsed time
        self.lastParse = now

        # Return the number of parsed records
        return len(data["aircraft"])


#
# Parser for ACARS messages coming from AcarsDec in JSON format.
#
class AcarsParser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="ACARS", service=service)
        self.attrMap = {
            "tail"   : "aircraft",
            "flight" : "flight",
            "text"   : "message",
            "dsta"   : "destination",
            "depa"   : "origin",
            "eta"    : "eta",
        }

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        #logger.debug("@@@ ACARS: {0}".format(data))
        # Collect basic data first
        out = {
            "mode"      : "ACARS",
            "type"      : "ACARS frame",
            "timestamp" : round(data["timestamp"] * 1000),
            "data"      : data
        }
        # Fetch other data
        for key in self.attrMap:
            if key in data:
                value = data[key].strip()
                if len(value)>0:
                    out[self.attrMap[key]] = value
        # Done
        return out
