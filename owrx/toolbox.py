from owrx.storage import DataRecorder
from owrx.config import Config
from owrx.color import ColorCache
from owrx.reporting import ReportingEngine
from csdr.module import ThreadModule, LineBasedModule
from pycsdr.types import Format
from owrx.dsame3.dsame import same_decode_string
from datetime import datetime, timezone
import pickle
import re
import json

import logging

logger = logging.getLogger(__name__)


class Mp3Recorder(ThreadModule, DataRecorder):
    def __init__(self, service: bool = False, maxBytes: int = 32 * 1024 * 1024):
        self.service = service
        DataRecorder.__init__(self, "REC", ".mp3", maxBytes)
        ThreadModule.__init__(self)

    def getInputFormat(self) -> Format:
        return Format.CHAR

    def getOutputFormat(self) -> Format:
        return Format.CHAR

    def run(self):
        while self.doRun:
            data = self.reader.read()
            if data is None:
                self.doRun = False
            else:
                self.writeFile(data)
        self.closeFile()


class TextParser(LineBasedModule, DataRecorder):
    def __init__(self, filePrefix: str = None, service: bool = False):
        self.service = service
        DataRecorder.__init__(self, filePrefix, ".txt")
        LineBasedModule.__init__(self)

    # Compose name of this decoder, made of client/service and frequency
    def myName(self):
        return "%s%s%s" % (
            "Service" if self.service else "Client",
            " " + self.filePfx if self.filePfx else "",
            " at %dkHz" % (self.frequency // 1000) if self.frequency>0 else ""
        )

    # By default, do not parse
    def parse(self, msg: bytes):
        return None

    def run(self):
        logger.info("%s starting..." % self.myName())
        super().run()
        logger.info("%s exiting..." % self.myName())
        self.closeFile()

    def process(self, line: bytes) -> any:
        # No result yet
        out = None

        try:
            #logger.debug("%s: %s" % (self.myName(), str(line)))
            # Let parse() function do its thing
            out = self.parse(line)
            # If running as a service and writing to a log file...
            if self.service and self.filePfx is not None:
                if out:
                    # If parser returned output, write it into log file
                    self.writeFile(str(out).encode("utf-8") + b"\n")
                elif out is None and len(line)>0:
                    # Write input into log file, including end-of-line
                    self.writeFile(line + b"\n")

        except Exception as exptn:
            logger.error("%s: Exception parsing: %s" % (self.myName(), str(exptn)))

        # Return parsed result, ignore result in service mode
        return out if out and not self.service else None


class RdsParser(TextParser):
    def __init__(self, service: bool = False):
        # Data will be accumulated here
        self.rds = { "mode": "WFM" }
        # Construct parent object
        super().__init__(filePrefix="WFM", service=service)

    def parse(self, msg: bytes):
        # Do not parse in service mode
        if self.service:
            return None
        # Expect JSON data in text form
        data = json.loads(msg)
        # Delete constantly changing group ID
        data.pop("group", None)
        # Clear data when PI changes
        if data.get("pi") != self.rds.get("pi"):
            if "frequency" in self.rds:
                self.rds = { "mode": "WFM", "frequency": self.rds["frequency"] }
            else:
                self.rds = { "mode": "WFM" }
        # Only update if there is new data
        if data.items() <= self.rds.items():
            return None
        else:
            self.rds.update(data)
            return self.rds

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
        # Clear RDS data when frequency changed
        self.rds = { "mode": "WFM", "frequency": frequency }


class IsmParser(TextParser):
    def __init__(self, service: bool = False):
        # Colors will be assigned via this cache
        self.colors = ColorCache()
        # Construct parent object
        super().__init__(filePrefix="ISM", service=service)

    def parse(self, msg: bytes):
        # Expect JSON data in text form
        out = json.loads(msg)
        # Add mode name
        out["mode"] = "ISM"
        # Convert Unix timestamps to milliseconds
        if "time" in out:
            out["timestamp"] = int(out["time"]) * 1000
            del out["time"]
        # Add frequency, if known
        if self.frequency:
            out["freq"] = self.frequency
        # Report message
        ReportingEngine.getSharedInstance().spot(out)
        # In interactive mode, color messages based on sender IDs
        if not self.service:
            out["color"] = self.colors.getColor(out["id"])
        # Always return JSON data
        return out


class PageParser(TextParser):
    def __init__(self, service: bool = False):
        # When true, try filtering out unreadable messages
        pm = Config.get()
        self.filtering = "paging_filter" in pm and pm["paging_filter"]
        # POCSAG<baud>: Address: <num> Function: <hex> (Certainty: <num> )?(Numeric|Alpha|Skyper): <message>
        self.rePocsag = re.compile(r"POCSAG(\d+):\s*Address:\s*(\S+)\s+Function:\s*(-?\d+)(\s+Certainty:\s*(-?\d+))?(\s+(\S+):\s*(.*))?")
        # FLEX|NNNN-NN-NN NN:NN:NN|<baud>/<value>/C/C|NN.NNN|NNNNNNNNN|<type>|<message>
        # FLEX|NNNN-NN-NN NN:NN:NN|<baud>/<value>/C/C|NN.NNN|NNNNNNNNN NNNNNNNNN|<type>|<message>
        self.reFlex1 = re.compile(r"FLEX\|(\d\d\d\d-\d\d-\d\d\s+\d\d:\d\d:\d\d)\|(\d+)/(\d+/\S/\S)\|(\d\d\.\d\d\d)\|(\d+(?:\s+\d+){0,})\|(\S+)\|(.*)")
        # FLEX: NNNN-NN-NN NN:NN:NN <baud>/<value>/C NN.NNN [NNNNNNNNN] <type> <message>
        self.reFlex2 = re.compile(r"FLEX:\s+(\d\d\d\d-\d\d-\d\d\s+\d\d:\d\d:\d\d)\s+(\d+)/(\d+/\S)\s+(\d\d\.\d\d\d)\s+\[(\d+)\]\s+(\S+)\s+(.*)")
        # FLEX message status
        self.reFlex3 = re.compile(r"(\d+)(/\S)?/\S")
        # Message filtering patterns
        self.reControl = re.compile(r"<[\w\d]{2,3}>")
        self.reSpaces = re.compile(r"[\000-\037\s]+")
        # Fragmented messages will be assembled here
        self.flexBuf = {}
        # Colors will be assigned via this cache
        self.colors = ColorCache()
        # Construct parent object
        super().__init__(filePrefix="PAGE", service=service)

    def parse(self, msg: bytes):
        # No result yet
        out = None
        # Steer message to POCSAG or FLEX parser
        if msg.startswith(b"POCSAG"):
            out = self.parsePocsag(msg.decode("utf-8", "replace"))
        elif msg.startswith(b"FLEX"):
            out = self.parseFlex(msg.decode("utf-8", "replace"))
        # Ignore filtered messages
        if not out:
            return {}
        # Add frequency, if known
        if self.frequency:
            out["freq"] = self.frequency
        # Report message
        ReportingEngine.getSharedInstance().spot(out)
        # In interactive mode, color messages based on addresses
        if not self.service:
            out["color"] = self.colors.getColor(out["address"])
        # Always return JSON data
        return out

    def collapseSpaces(self, msg: str) -> str:
        # Collapse white space
        return self.reSpaces.sub(" ", msg).strip()

    def isReadable(self, msg: str) -> bool:
       # Consider string human-readable if the average word length
       # is sufficiently small
       spaces  = msg.count(" ")
       letters = len(msg) - spaces
       return (letters > 0) and (letters / (spaces+1) < 40)

    def parsePocsag(self, msg: str):
        # No result yet
        out = None

        # Parse POCSAG messages
        r = self.rePocsag.match(msg)
        if r is not None:
            baud      = r.group(1)
            capcode   = r.group(2)
            function  = r.group(3)
            certainty = r.group(5)
            msgtype   = "" if not r.group(7) else r.group(7)
            msg       = "" if not r.group(8) else r.group(8)

            # Remove POCSAG "<XXX>" sequences and collapse white space
            msg = self.collapseSpaces(self.reControl.sub(" ", msg))

            # When filtering, only output readable messages
            if not self.filtering or (msgtype=="Alpha" and len(msg)>0):
                out = {
                    "mode":      "POCSAG",
                    "baud":      int(baud),
                    "timestamp": round(datetime.now().timestamp() * 1000),
                    "address":   capcode,
                    "function":  int(function),
                    "type":      msgtype,
                    "message":   msg
                }
                # Output type, message, and certainty
                if len(msgtype)>0:
                    out["type"] = msgtype
                if len(msg)>0:
                    out["message"] = msg
                if certainty is not None:
                    out["certainty"] = int(certainty)

        # Done
        return out

    def parseFlex(self, msg: str):
        # No result yet
        out = None

        # Parse FLEX messages
        r = self.reFlex1.match(msg)
        r = self.reFlex2.match(msg) if not r else r
        if r is not None:
            time    = datetime.strptime(r.group(1), "%Y-%m-%d %H:%M:%S")
            time    = time.replace(tzinfo=timezone.utc)
            baud    = r.group(2)
            state   = r.group(3)
            frame   = r.group(4)
            capcode = r.group(5)
            msgtype = r.group(6)
            msg     = r.group(7)
            rm      = self.reFlex3.match(state)
            channel = "" if not rm else rm.group(1)
            frag    = "" if not rm or not rm.group(2) else rm.group(2)[1]
            # Assemble fragmented messages in flexBuf
            if frag == "F" or frag == "C":
                # Do not let flexBuf grow too much
                if len(self.flexBuf)>1024:
                    self.flexBuf = {}
                # Accumulate messages in flexBuf, index by capcode
                if capcode in self.flexBuf:
                    self.flexBuf[capcode] += msg
                else:
                    self.flexBuf[capcode] = msg
                # Output message once it completes
                if frag == "C":
                    msg = self.flexBuf[capcode]
                    del self.flexBuf[capcode]
            # Do not report fragments of messages
            if frag != "F":
                # Collapse white space
                msg = self.collapseSpaces(msg)
                # When filtering, only output readable messages
                if not self.filtering or (msgtype=="ALN" and self.isReadable(msg)):
                    out = {
                        "mode":      "FLEX",
                        "baud":      int(baud),
                        "timestamp": round(datetime.now().timestamp() * 1000),
                        "state":     state,
                        "frame":     frame,
                        "address":   capcode,
                        "type":      msgtype
                    }
                    # Output channel
                    if len(channel)>0:
                        out["channel"] = int(channel)
                    # Output message
                    if len(msg)>0:
                        out["message"] = msg

        # Done
        return out


class SelCallParser(TextParser):
    def __init__(self, service: bool = False):
        self.reSplit = re.compile(r"(ZVEI1|ZVEI2|ZVEI3|DZVEI|PZVEI|DTMF|EEA|EIA|CCIR):\s+")
        self.reMatch = re.compile(r"ZVEI1|ZVEI2|ZVEI3|DZVEI|PZVEI|DTMF|EEA|EIA|CCIR")
        self.mode = ""
        # Construct parent object
        super().__init__(filePrefix="SELCALL", service=service)

    def parse(self, msg: bytes):
        # Do not parse in service mode
        if self.service:
            return None
        # Parse SELCALL messages
        msg = msg.decode("utf-8", "replace")
        dec = None
        out = ""
        r = self.reSplit.split(msg)

        for s in r:
            if self.reMatch.match(s):
                dec = s
            elif dec is not None and len(s)>0:
                if dec != self.mode:
                    out += "[" + dec + "] "
                    self.mode = dec
                out += s + " "
                dec = None
        # Done
        return out


class EasParser(TextParser):
    def __init__(self, service: bool = False):
        self.reSplit = re.compile(r"(EAS: \S+)")
        # Construct parent object
        super().__init__(filePrefix="EAS", service=service)

    def parse(self, msg: bytes):
        # Parse EAS SAME messages
        msg = msg.decode("utf-8", "replace")
        out = []

        for s in self.reSplit.split(msg):
            if not s.startswith("EAS: "):
                continue
            decoded = same_decode_string(s)
            if not decoded:
                continue
            for d in decoded:
                out += [s, d["msg"], ""]
                spot = {
                    "mode":      "EAS",
                    "timestamp": round(datetime.now().timestamp() * 1000),
                    "message":   d["msg"],
                    "raw":       s,
                    **d
                }
                # Remove stuff we do not need
                del spot["msg"]
                # Convert start and end times to UTC
                spot["start_time"] = spot["start_time"].astimezone(timezone.utc).isoformat()
                spot["end_time"] = spot["end_time"].astimezone(timezone.utc).isoformat()
                # Add frequency, if known
                if self.frequency:
                    spot["freq"] = self.frequency
                # Report received message
                ReportingEngine.getSharedInstance().spot(spot)

        # Return received message as text
        return "\n".join(out)

