from owrx.storage import Storage
from owrx.config import Config
from owrx.color import ColorCache
from owrx.reporting import ReportingEngine
from csdr.module import LineBasedModule
from pycsdr.types import Format
from datetime import datetime, timezone
import pickle
import os
import re
import json

import logging

logger = logging.getLogger(__name__)

class TextParser(LineBasedModule):
    def __init__(self, filePrefix: str = None, service: bool = False):
        self.service   = service
        self.frequency = 0
        self.data      = bytearray(b'')
        self.filePfx   = filePrefix
        self.file      = None
        self.maxLines  = 10000
        self.cntLines  = 0
        super().__init__()

    def __del__(self):
        # Close currently open file, if any
        self.closeFile()

    def closeFile(self):
        if self.file is not None:
            try:
                logger.debug("Closing log file '%s'." % self.file.name)
                self.file.close()
                self.file = None
                # Delete excessive files from storage
                logger.debug("Performing storage cleanup...")
                Storage.getSharedInstance().cleanStoredFiles()

            except Exception as exptn:
                logger.debug("Exception closing file: %s" % str(exptn))
                self.file = None

    def newFile(self, fileName):
        self.closeFile()
        try:
            logger.debug("Opening log file '%s'..." % fileName)
            self.file = Storage.getSharedInstance().newFile(fileName, buffering = 0)
            self.cntLines = 0

        except Exception as exptn:
            logger.debug("Exception opening file: %s" % str(exptn))
            self.file = None

    def writeFile(self, data):
        # If no file open, create and open a new file
        if self.file is None and self.filePfx is not None:
            self.newFile(Storage.makeFileName(self.filePfx+"-{0}", self.frequency) + ".txt")
        # If file open now...
        if self.file is not None:
            # Write new line into the file
            try:
                self.file.write(data)
            except Exception as exptn:
                logger.debug("Exception writing file: %s" % str(exptn))
            # No more than maxLines per file
            self.cntLines = self.cntLines + 1
            if self.cntLines >= self.maxLines:
                self.closeFile()

    def getInputFormat(self) -> Format:
        return Format.CHAR

    def getOutputFormat(self) -> Format:
        return Format.CHAR

    def setDialFrequency(self, frequency: int) -> None:
        self.frequency = frequency

    # Compose name of this decoder, made of client/service and frequency
    def myName(self):
        return "%s%s%s" % (
            "Service" if self.service else "Client",
            " " + self.filePfx if self.filePfx else "",
            " at %dkHz" % (self.frequency // 1000) if self.frequency>0 else ""
        )

    # Get current UTC time in a standardized format
    def getUtcTime(self) -> str:
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # By default, do not parse
    def parse(self, msg: bytes):
        return None

    def run(self):
        logger.debug("%s starting..." % self.myName())
        super().run()
        logger.debug("%s exiting..." % self.myName())

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
                    self.writeFile(str(out).encode("utf-8"))
                    self.writeFile(b"\n")
                elif out is None and len(line)>0:
                    # Write input into log file, including end-of-line
                    self.writeFile(line)
                    self.writeFile(b"\n")

        except Exception as exptn:
            logger.debug("%s: Exception parsing: %s" % (self.myName(), str(exptn)))

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
        self.reFlex1 = re.compile(r"FLEX\|(\d\d\d\d-\d\d-\d\d\s+\d\d:\d\d:\d\d)\|(\d+/\d+/\S/\S)\|(\d\d\.\d\d\d)\|(\d+(?:\s+\d+)?)\|(\S+)\|(.*)")
        # FLEX: NNNN-NN-NN NN:NN:NN <baud>/<value>/C NN.NNN [NNNNNNNNN] <type> <message>
        self.reFlex2 = re.compile(r"FLEX:\s+(\d\d\d\d-\d\d-\d\d\s+\d\d:\d\d:\d\d)\s+(\d+/\d+/\S)\s+(\d\d\.\d\d\d)\s+\[(\d+)\]\s+(\S+)\s+(.*)")
        # FLEX message status
        self.reFlex3 = re.compile(r"(\d+/\d+)(/\S)?/\S")
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
            out = self.parsePocsag(msg.decode('utf-8', 'replace'))
        elif msg.startswith(b"FLEX"):
            out = self.parseFlex(msg.decode('utf-8', 'replace'))
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
                    "baud":      baud,
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
            state   = r.group(2)
            frame   = r.group(3)
            capcode = r.group(4)
            msgtype = r.group(5)
            msg     = r.group(6)
            rm      = self.reFlex3.match(state)
            baud    = "" if not rm else rm.group(1)
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
            # Only output message once it completes
            if frag == "F":
                msg = ""
            elif frag == "C":
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
                        "baud":      baud,
                        "timestamp": round(time.timestamp() * 1000),
                        "state":     state,
                        "frame":     frame,
                        "address":   capcode,
                        "type":      msgtype
                    }
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
        msg = msg.decode('utf-8', 'replace')
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

class EasSameParser(TextParser):
    def __init__(self, service: bool = False):
        self.reSplit = re.compile(r"(EAS: \S+)")
        # Construct parent object
        super().__init__(filePrefix="EAS_SAME", service=service)

    def parse(self, msg: bytes):
        # Parse EAS SAME messages
        from dsame3_simple.dsame import same_decode_string
        msg = msg.decode('utf-8', 'replace')
        out = []

        r = self.reSplit.split(msg)
        for s in r:
            if not s.startswith('EAS: '):
                continue
            dec = same_decode_string(s)
            if not dec:
                continue
            for d in dec:
                out += [s, d['msg'], '']
                spot = {
                    **d,
                    "mode":      "EAS_SAME",
                    "timestamp": self.getUtcTime(),
                    "message":   d['msg'],
                    "raw":       s
                }
                del spot['msg']
                ReportingEngine.getSharedInstance().spot(spot)

        if self.service:
            return None

        return '\n'.join(out)
