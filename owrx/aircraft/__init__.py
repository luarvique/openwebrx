from owrx.aircraft.icao import IcaoRegistration, IcaoCountry
from owrx.aircraft.manager import AircraftManager

from owrx.toolbox import TextParser
from owrx.config import Config
from owrx.reporting import ReportingEngine

from datetime import datetime, timedelta, timezone

import threading
import pickle
import json
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
        #logger.debug(f"ACARS: {data}")
        # Look up human-readable frame type
        label = data["label"]
        if label not in ACARS_LABELS:
            out["type"] = "ACARS frame with label [" + label + "]"
        else:
            msgType = ACARS_LABELS[label]
            out["type"] = msgType[2]
            if msgType[0] == 1:
                out["direction"] = "D"
            elif msgType[0] == 2:
                out["direction"] = "U"
            elif msgType[0] == 4:
                out["direction"] = "G"

        # Collect data
        for key in ACARS_FIELDS:
            if key in data:
                value = data[key].strip()
                if len(value)>0:
                    out[ACARS_FIELDS[key]] = value

        # Parse position reports
        if "message" in out and out["message"].startswith("POS"):
            self.parsePosReport(out["message"], out)

        # Parse frequency change requests
        if label == ":;":
            try:
                fMHz = int(out["message"]) / 1000
                out["message"] = f"Change frequency to {fMHz}MHz"
            except ValueError:
                logger.error("Failed to parse frequency: '{0}'".format(out["message"]))

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
                elif "predicted_route" in tag:
                    pos = tag["predicted_route"]
                    route = []
                    for k in ["next_wpt", "next_next_wpt"]:
                        if k in pos:
                            v = pos[k]
                            wpt = { "lat": v["lat"], "lon": v["lon"] }
                            if "alt" in v:
                                wpt["altitude"] = v["alt"]
                            if "eta_sec" in v:
                                wpt["timestamp"] = out["timestamp"] + v["eta_sec"] * 1000
                            route.append(wpt)
                    if len(route) > 0:
                        out["route"] = route
                else:
                    out["message"] += (",\n" if out["message"] else "") + str(tag)
                # TODO: Parse other types

        # Done
        return out

    # Parse single LatLon value
    def parseLatLon(self, text, out):
        m = re.match(r"^([NS])(\d+)([WE])(\d+),(.*)$", text)
        if not m:
            return None
        else:
            # Degrees and minutes to fractional degrees
            lat = int(m.group(2))
            lon = int(m.group(4))
            lat = (lat // 1000) + (lat % 1000) / 10 / 60
            lon = (lon // 1000) + (lon % 1000) / 10 / 60
            out["lat"] = lat * (1 if m.group(1) == "N" else -1)
            out["lon"] = lon * (1 if m.group(3) == "E" else -1)
            return m.group(5)

    # Parse single waypoint + time + flight level
    def parseWaypoint(self, text, out):
        # Try parsing LatLon first
        tail = self.parseLatLon(text, out)
        # If failed, try parsing fix name
        if not tail:
            m = re.match(r"^([A-Z]+[0-9A-Z\-]*),(.*)$", text)
            if not m:
                return None
            else:
                out["name"] = m.group(1)
                tail = m.group(2)
        # Parse time and altitude
        m = re.match(r"^(\d{6}),((\d+),)?(.*)$", tail)
        if not m:
            return tail
        else:
            # UTC HHMMSS to milliseconds
            hms  = m.group(1)
            now  = datetime.now(timezone.utc)
            time = now.replace(hour=int(hms[0:2]), minute=int(hms[2:4]), second=int(hms[4:6]))
            if time < now:
                time += timedelta(days=1)
            out["time"] = round(time.timestamp() * 1000)
            # Flight level to feet
            if m.group(2):
                out["altitude"] = int(m.group(3)) * 100
            # Done
            return m.group(4)

    # Parse enviromental conditions
    def parseEnvironment(self, text, out):
        m = re.match(r"^([MP])(\d+),(\d{3})(\d{1,3}),(.*)$", text)
        if not m:
            return None
        else:
            out["temperature"] = int(m.group(2)) * (1 if m.group(1) == "P" else -1)
            out["wind"]  = { "course": int(m.group(3)), "speed": int(m.group(4)) }
            return m.group(5)

    # Parse ACARS position report
    def parsePosReport(self, posReport, out):
        # Must start with POS
        if not posReport.startswith("POS"):
            return False
        logger.debug(f"Parsing position report: '{posReport}'...")

        # Parse current position
        posReport = self.parseLatLon(posReport[3:].replace(" ", ""), out)
        if not posReport:
            return False

        # Parse message body (route + environment)
        route = []
        while True:
            # Try parsing environment (temperature + wind) first
            tail = self.parseEnvironment(posReport, out)
            if tail:
                break
            # Try parsing next waypoint
            wpt = {}
            tail = self.parseWaypoint(posReport, wpt)
            if not tail:
                break
            # Waypoint parsed
            route.append(wpt)
            posReport = tail

        # If we have got a route...
        if len(route) > 0:
            logger.debug(f"Parsed route: {route}")
            # Save route
            out["route"] = route
            # Assume closest waypoint altitude to be current
            if "altitude" in route[0]:
                out["altitude"] = route[0]["altitude"]

        # Done
        return True


#
# Parser for HFDL messages coming from DumpHFDL in JSON format.
#
class HfdlParser(AircraftParser):
    def __init__(self, service: bool = False):
        super().__init__(filePrefix="HFDL", service=service)

    def parseAircraft(self, msg: bytes):
        # Expect JSON data in text form
        data = json.loads(msg)
        #logger.debug(f"HFDL: {data}")
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
        #logger.debug(f"VDL2: {data}")
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
                    if not self.service and self.writer and parsed > 0:
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
        #logger.debug("UAT: {0}".format(data))

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
        #logger.debug(f"ACARS: {data}")
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
            "rssi"      : data["level"],
            "data"      : data
        }
        # Parse ACARS frame
        self.parseAcars(data, out)
        # Done
        return out

