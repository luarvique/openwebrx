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

# Conversion factor from mach numbers to knots
MACH_TO_KNOTS = 666.738661


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
  "UAT":   (0, 0)
}

#
# ACARS message labels (0: N/A, 1: downlink, 2: uplink, 3: both, 4: ground)
#
ACARS_LABELS = {
    "_j" : (0, "---", "No Information to Send"),
    "_d" : (3, "---", "Acknowledgement"),
    "00" : (1, "HJK", "Emergency Situation Report"),
    "14" : (5, "???", "General Aviation Free Text"),
    "15" : (5, "???", "General Aviation Position Report"),
    "16" : (5, "???", "General Aviation Weather Request"),
    "2S" : (0, "---", "Weather Request"),
    "2U" : (0, "---", "Weather"),
    "4M" : (0, "---", "Cargo Information"),
    "51" : (0, "---", "Ground GMT Request Response"),
    "52" : (0, "AGM", "Ground UTC Request"),
    "54" : (3, "---", "Aircrew Initiated Voice Contact Request"),
    "57" : (1, "AEP", "Alternate Aircrew Initiated Position Report"),
    "5D" : (1, "TIS", "ATIS Request"),
    "5P" : (1, "---", "Temporary Suspension of ACARS"),
    "5R" : (1, "AEP", "Aircraft Initiated Position Report"),
    "5U" : (1, "WXR", "Weather Request"),
    "5Y" : (1, "ETA", "Revision to Previous ETA"),
    "5Z" : (1, "AGM", "Airline Designated Downlink"),
    "7A" : (1, "ENG", "Aircraft Initiated Engine Data"),
    "7B" : (1, "ABM", "Aircraft Initiated Miscellaneous Message"),
    "80" : (1, "---", "Aircraft Addressed Downlink #1"),
    "81" : (1, "---", "Aircraft Addressed Downlink #2"),
    "82" : (1, "---", "Aircraft Addressed Downlink #3"),
    "83" : (1, "---", "Aircraft Addressed Downlink #4"),
    "84" : (1, "---", "Aircraft Addressed Downlink #5"),
    "85" : (1, "---", "Aircraft Addressed Downlink #6"),
    "86" : (1, "---", "Aircraft Addressed Downlink #7"),
    "87" : (1, "---", "Aircraft Addressed Downlink #8"),
    "88" : (1, "---", "Aircraft Addressed Downlink #9"),
    "89" : (1, "---", "Aircraft Addressed Downlink #10"),
    "A1" : (2, "CLX", "Deliver Oceanic Clearance"),
    "A2" : (2, "CLD", "Deliver Departure Clearance"),
    "A4" : (2, "RCA", "Acknowledge PDC"),
    "A5" : (2, "RPR", "Request Position Report"),
    "A6" : (2, "RAR", "Request ADS Report"),
    "A7" : (2, "FTU", "Forward Free Text to Aircraft"),
    "A8" : (2, "DDS", "Deliver Departure Slot"),
    "A9" : (2, "DAI", "Deliver ATIS Information"),
    "A0" : (2, "AFN", "ATIS Facilities Notification"),
    "B1" : (1, "RCL", "Request Oceanic Clearance"),
    "B2" : (1, "CLA", "Request Oceanic Readback"),
    "B3" : (1, "RCD", "Request Departure Clearance"),
    "B4" : (1, "---", "Acknowledge Departure Clearance"),
    "B5" : (1, "PPR", "Provide Position Report"),
    "B6" : (1, "PAR", "Provide ADS Report"),
    "B7" : (1, "FTD", "Forward Free Text to ATS"),
    "B8" : (1, "RDS", "Request Departure Slot"),
    "B9" : (1, "RAI", "Request ATIS Information"),
    "C0" : (2, "---", "Uplink Message to All Cockpit Printers"),
    "C1" : (2, "---", "Uplink Message to Cockpit Printer #1"),
    "C2" : (2, "---", "Uplink Message to Cockpit Printer #2"),
    "C3" : (2, "---", "Uplink Message to Cockpit Printer #3"),
    "CA" : (0, "---", "Printer Error"),
    "CB" : (4, "---", "Printer Busy"),
    "CC" : (4, "---", "Printer in Local or Test Mode"),
    "CD" : (4, "---", "Printer Out of Paper"),
    "CE" : (4, "---", "Printer Buffer Overrun"),
    "CF" : (4, "---", "Printer Reserved"),
    "F3" : (1, "---", "Dedicated Transceiver Advisory"),
    "H1" : (3, "---", "General Message"),
    "H2" : (5, "???", "Meteorological Report"),
    "H3" : (5, "???", "Icing Report"),
    "HF" : (5, "???", "HFDL Message"),
    "HX" : (1, "REJ", "Undelivered Uplink Report"),
    "M1" : (1, "MVA", "IATA Departure Message"),
    "M2" : (1, "MVA", "IATA Arrival Message"),
    "M3" : (1, "MVA", "IATA Return to Ramp Message"),
    "M4" : (1, "MVA", "IATA Return from Airborne Message"),
    "Q0" : (0, "---", "ACARS Link Test"),
    "Q1" : (1, "ETA", "Departure/Arrival Reports"),
    "Q2" : (1, "ETA", "ETA Reports"),
    "Q3" : (1, "CLK", "Clock Update"),
    "Q4" : (2, "---", "Voice Circuit Busy (response to 54)"),
    "Q5" : (4, "---", "Unable to Process Uplinked Messages"),
    "Q6" : (1, "---", "Voice-to-ACARS Change-Over"),
    "Q7" : (1, "DLA", "Delay Message"),
    "QA" : (1, "DEP", "OUT: Fuel Report"),
    "QB" : (1, "DEP", "OFF Report"),
    "QC" : (1, "ARR", "ON Report"),
    "QD" : (1, "ARR", "IN: Fuel Report"),
    "QE" : (1, "DEP", "OUT: Duel Destination Report"),
    "QF" : (1, "DEP", "OFF: Destination Report"),
    "QG" : (1, "RTN", "OUT: Return in Report"),
    "QH" : (1, "DEP", "OUT Report"),
    "QK" : (1, "ARR", "Landing Report"),
    "QL" : (1, "ARR", "Arrival Report"),
    "QM" : (1, "ARR", "Arrival Information Report"),
    "QN" : (1, "DIV", "Diversion Report"),
    "QR" : (5, "???", "ON Report"),
    "QS" : (5, "???", "IN Report"),
    "QT" : (5, "???", "OUT: Return IN Report"),
    "QX" : (1, "---", "Intercept"),
    "RA" : (2, "RPR", "Tell Aircraft Terminal to Transmit Data"),
    "RB" : (1, "---", "Aircraft Terminal Response to RA Message"),
    "S1" : (5, "???", "VHF Network Statistics Report"),
    "S2" : (5, "???", "VHF Performance Report"),
    "S3" : (5, "???", "LRU Configuration Report"),
    "SA" : (5, "???", "Media Advisory"),
    "SQ" : (2, "???", "Squitter Message"),
    ":;" : (2, "---", "Tell Aircraft to Change Frequency")
}

#
# ACARS field mapping
#
ACARS_FIELDS = {
    "reg"      : "aircraft",
    "tail"     : "aircraft",
    "flight"   : "flight",
    "text"     : "message",
    "msg_text" : "message",
    "dsta"     : "destination",
    "depa"     : "origin",
    "eta"      : "eta",
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


#
# Base class for aircraft message parsers.
#
class AircraftParser(TextParser):
    def __init__(self, filePrefix: str = None, service: bool = False):
        self.reFlight = re.compile(r"^([0-9A-Z]{2}|[A-Z]{3})0*([0-9]+[A-Z]*)$")
        self.reDots   = re.compile(r"^\.*([^\.].*?)\.*$")
        self.reIATA   = re.compile(r"^..[0-9]+$")
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

    # Common function to parse ACARS subframes in ACARS/HFDL/VDL2/etc
    def parseAcars(self, data, out):
        #logger.debug("@@@ ACARS: {0}".format(data))
        # Look up human-readable frame type
        label = data["label"]
        if label not in ACARS_LABELS:
            out["type"] = "ACARS frame with label [" + label + "]"
        else:
            label = ACARS_LABELS[label]
            out["type"] = label[2]
            if label[0] == 1:
                out["direction"] = "D"
            elif label[0] == 2:
                out["direction"] = "U"
            elif label[0] == 4:
                out["direction"] = "G"

        # Collect data
        for key in ACARS_FIELDS:
            if key in data:
                value = data[key].strip()
                if len(value)>0:
                    out[ACARS_FIELDS[key]] = value

        # Parse frequency change requests
        if label == ":;":
            try:
                fMHz = int(out["message"]) / 1000
                out["type"] = "Aircraft to Change Frequency to " + fMHz  + "MHz"
                out.pop("message", None)
            except ValueError:
                pass

        # Look for ARINC622 data decoded by LibACARS
        if "libacars" in data and "arinc622" in data["libacars"]:
            self.parseArinc622(data["libacars"]["arinc622"], out)

        # Done
        return out

    # Parse ARINC622 information produced by LibACARS
    def parseArinc622(self, data, out):
        type = data["msg_type"].replace("_", " ").upper()
        out["type"] = f"ARINC622 {type}"
        out["aircraft"] = data["air_addr"]
        out["gs"] = data["gs_addr"]

        # CPDLC messages...
        if "cpdlc" in data:
            # Remove original message from output
            out.pop("message", None)
            # Parse CPDLC message
            self.parseCpdlc(data["cpdlc"], out)

        # ADS-C messages...
        if "adsc" in data:
            # Remove original message from output
            out.pop("message", None)
            # Parse ADSC message
            self.parseAdsc(data["adsc"], out)

        # Done
        return out

    # Parse ARINC622 CPDLC information produced by LibACARS
    def parseCpdlc(self, data, out):
        # Determine message direction and get data
        if "atc_downlink_msg" in data:
            out["direction"] = "D"
            ts   = data["atc_downlink_msg"]["header"]["timestamp"]
            data = data["atc_downlink_msg"]["atc_downlink_msg_element_id"]
        elif "atc_uplink_msg" in data:
            out["direction"] = "U"
            ts = data["atc_uplink_msg"]["header"]["timestamp"]
            data = data["atc_uplink_msg"]["atc_uplink_msg_element_id"]
        else:
            return None

        # Parse explicit timestamp
        out["msgtime"] = "%02d:%02d:%02d" % (ts["hour"], ts["min"], ts["sec"])

        # Parse message contents
        if "free_text" in data["data"]:
            out["message"] = data["data"]["free_text"]
        elif data["data"]:
            out["message"] = data["choice_label"] + ":\n" + str(data["data"])
        else:
            out["message"] = data["choice_label"]
        # TODO: Parse other data fields

        # Done
        return out

    # Parse ARINC622 ADS-C information produced by LibACARS
    def parseAdsc(self, data, out):
        # ADS-C messages always go down from aircraft
        out["direction"] = "D"
        out["message"] = ""

        # Look for position reports
        if "tags" in data:
            for tag in data["tags"]:
                if "flight_id" in tag:
                    out["flight"] = tag["flight_id"]["flight_id"]
                elif "basic_report" in tag:
                    pos = tag["basic_report"]
                    out["lat"] = pos["lat"]
                    out["lon"] = pos["lon"]
                    out["altitude"] = pos["alt"]
                elif "air_ref_data" in tag:
                    pos = tag["air_ref_data"]
                    if "speed" not in out:
                        out["speed"]  = round(pos["spd_mach"] * MACH_TO_KNOTS)
                        out["vspeed"] = round(pos["vspd_ftmin"])
                    if pos["true_hdg_valid"] and "course" not in out:
                        out["course"] = round(pos["true_hdg_deg"])
                elif "earth_ref_data" in tag:
                    # Making this preferable to air_ref_data
                    pos = tag["earth_ref_data"]
                    out["speed"]  = round(pos["gnd_spd_kts"])
                    out["vspeed"] = round(pos["vspd_ftmin"])
                    if pos["true_trk_valid"]:
                        out["course"] = round(pos["true_trk_deg"])
                elif "meteo_data" in tag:
                    pos = tag["meteo_data"]
                    wind = { "speed": round(pos["wind_spd_kts"]) }
                    if pos["wind_dir_valid"]:
                        wind["course"] = round(pos["wind_dir_true_deg"])
                    out["temperature"] = pos["temp_c"]
                    out["wind"] = wind
                else:
                    out["message"] += (",\n" if out["message"] else "") + str(tag)
                # TODO: Parse other types

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
        if "hfdl" not in data or "lpdu" not in data["hfdl"]:
            return None
        data = data["hfdl"]
        # Collect basic data first
        out = {
            "mode"      : "HFDL",
            "timestamp" : round(data["t"]["sec"] * 1000 + data["t"]["usec"] / 1000),
            "data"      : data
        }
        # Parse LPDU if present
        if "lpdu" in data:
            self.parseLpdu(data["lpdu"], out)
        # Parse SPDU if present
        if "spdu" in data:
            self.parseSpdu(data["spdu"], out)
        # Parse MPDU if present
        if "mpdu" in data:
            self.parseMpdu(data["mpdu"], out)
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
        # @@@ Only parse messages that have AVLC frames for now !!!
        if "vdl2" not in data or "avlc" not in data["vdl2"]:
            return None
        data = data["vdl2"]
        avlc = data["avlc"]
        # Ignore acknowledgements, if requested
        if self.isAvlcAck(avlc):
            pm = Config.get()
            if pm["vdl2_ignore_acks"]:
                return None
        # Collect basic data first
        out = {
            "mode"      : "VDL2",
            "timestamp" : round(data["t"]["sec"] * 1000 + data["t"]["usec"] / 1000),
            "data"      : data
        }
        # Parse AVLC
        self.parseAvlc(avlc, out)
        # Done
        return out

    # Return TRUE if AVLC frame is an acknowledgement
    def isAvlcAck(self, data):
        if "frame_type" in data and data["frame_type"] == "S":
            return True
        elif "acars" in data and "label" in data["acars"]:
            label = data["acars"]["label"]
            return label == "_j" or label == "_d"
        else:
            return False

    # Parse AVLC frame
    def parseAvlc(self, data, out):
        # Find if aircraft is message's source or destination
        if data["src"]["type"] == "Aircraft":
            out["direction"] = "D"
            p = data["src"]
        elif data["dst"]["type"] == "Aircraft":
            out["direction"] = "U"
            p = data["dst"]
        else:
            return None
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
# Parser for Dump1090 JSON file containing currently tracked aircraft.
#
class AdsbParser(AircraftParser):
    def __init__(self, service: bool = False, jsonFile: str = "/tmp/dump1090/aircraft.json"):
        super().__init__(filePrefix=None, service=service)
        self.jsonFile = jsonFile
        self.checkPeriod = 1
        self.lastParse = 0
        # Start periodic JSON file check
        self.stopEvent = threading.Event()
        self.thread = threading.Thread(target=self._refreshThread, name=type(self).__name__ + ".Refresh")
        self.thread.start()

    # Not parsing STDOUT
    def parseAircraft(self, msg: bytes):
        return None

    # To stop, need to terminate the thread first
    def stop(self):
        self.stopEvent.set()

    # Periodically check if Dump1090's JSON file has changed
    # and parse it if it has.
    def _refreshThread(self):
        lastUpdate = 0
        while not self.stopEvent.is_set():
            # If JSON file has updated since the last update, parse it
            try:
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
            # Wait until the next check or termination
            self.stopEvent.wait(self.checkPeriod)
        # Thread is done, free resources
        super().stop()

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

            # Update aircraft database
            if AircraftManager.getSharedInstance().update(out):
                # Report any new/updated data
                ReportingEngine.getSharedInstance().spot(out)

        # Save last parsed time
        self.lastParse = now

        # Return the number of parsed records
        return len(data["aircraft"])


#
# Parser for UAT messages coming from Dump978 in JSON format.
#
class UatParser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="UAT", service=service)

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        #logger.debug("@@@ UAT: {0}".format(data))

        # Collect basic data first
        out = {
            "mode"      : "UAT",
            "timestamp" : round(data["metadata"]["received_at"] * 1000),
            "rssi"      : data["metadata"]["rssi"],
            "icao"      : data["address"].upper(),
            "state"     : data["airground_state"],
            "lat"       : data["position"]["lat"],
            "lon"       : data["position"]["lon"],
            "data"      : data
        }

        # Aircraft
        if "callsign" in data and data["callsign"] != "UNKN":
            out["aircraft"] = data["callsign"].upper()
        if "emitter_category" in data:
            out["category"] = data["emitter_category"].upper()

        # Emergency status
        if "emergency" in data and data["emergency"] != "none":
            out["emergency"] = data["emergency"].upper()

        # Altitude
        if "geometric_altitude" in data:
            out["altitude"] = round(data["geometric_altitude"])
        elif "pressure_altitude" in data:
            out["altitude"] = round(data["pressure_altitude"])

        # Climb/descent rate
        if "vertical_velocity_geometric" in data:
            out["vspeed"] = round(data["vertical_velocity_geometric"])
        elif "vertical_velocity_barometric" in data:
            out["vspeed"] = round(data["vertical_velocity_barometric"])

        # Speed
        if "ground_speed" in data:
            out["speed"] = round(data["ground_speed"])

        # Heading
        if "true_track" in data:
            out["course"] = round(data["true_track"])

        # Get country and aircraft registration from ICAO ID
        self.parseIcaoId(data["address"], out)

        # Done
        return out


#
# Parser for ACARS messages coming from AcarsDec in JSON format.
#
class AcarsParser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="ACARS", service=service)

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        # Ignore acknowledgements, if requested
        label = data["label"]
        if label == "_j" or label == "_d":
            pm = Config.get()
            if pm["acars_ignore_acks"]:
                return None
        # Collect basic data first
        out = {
            "mode"      : "ACARS",
            "timestamp" : round(data["timestamp"] * 1000),
            "data"      : data
        }
        # Parse ACARS frame
        self.parseAcars(data, out)
        # Done
        return out

