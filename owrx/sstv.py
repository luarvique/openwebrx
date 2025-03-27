from owrx.storage import Storage, DataRecorder
from csdr.module import ThreadModule
from pycsdr.types import Format
from datetime import datetime
import base64
import pickle
import os

import logging

logger = logging.getLogger(__name__)

modeNames = {
    0:  "Robot 12",
    4:  "Robot 24",
    8:  "Robot 36",
    12: "Robot 72",
    32: "Martin 4",
    36: "Martin 3",
    40: "Martin 2",
    44: "Martin 1",
    48: "Scottie 4",
    51: "SC2 30",
    52: "Scottie 3",
    55: "SC2 180",
    56: "Scottie 2",
    59: "SC2 60",
    60: "Scottie 1",
    63: "SC2 120",
    68: "AVT 90",
    76: "Scottie DX",
    93: "PD 50",
    94: "PD 290",
    95: "PD 120",
    96: "PD 180",
    97: "PD 240",
    98: "PD 160",
    99: "PD 90",

    # Unsupported modes
    1:  "Robot BW8R",
    2:  "Robot BW8G",
    3:  "Robot BW8B",
    5:  "Robot BW12R",
    6:  "Robot BW12G",
    7:  "Robot BW12B",
    9:  "Robot BW24R",
    10: "Robot BW24G",
    11: "Robot BW24B",
    13: "Robot BW36R",
    14: "Robot BW36G",
    15: "Robot BW36B",
    41: "Martin HQ1",
    42: "Martin HQ2",
    85: "FAX480",
    90: "FAST FM",
    100: "Proskan J120",
    104: "MSCAN TV-1",
    105: "MSCAN TV-2",
    113: "Pasokon P3",
    114: "Pasokon P5",
    115: "Pasokon P7",
}

class SstvParser(DataRecorder, ThreadModule):
    def __init__(self, service: bool = False):
        self.service = service
        self.data    = bytearray(b'')
        self.width   = 0
        self.height  = 0
        self.line    = 0
        self.mode    = 0
        DataRecorder.__init__(self, "SSTV", ".bmp")
        ThreadModule.__init__(self)

    def getInputFormat(self) -> Format:
        return Format.CHAR

    def getOutputFormat(self) -> Format:
        return Format.CHAR

    def myName(self):
        return "%s%s" % (
            "Service" if self.service else "Client",
            " at %dkHz" % (self.frequency // 1000) if self.frequency>0 else ""
        )

    def run(self):
        logger.debug("%s starting..." % self.myName())
        # Run while there is input data
        while self.doRun:
            # Read input data
            inp = self.reader.read()
            # Terminate if no input data
            if inp is None:
                self.doRun = False
                break
            # Add read data to the buffer
            self.data = self.data + inp.tobytes()
            # Process buffer contents
            out = self.process()
            # Keep processing while there is input to parse
            while out is not None:
                if len(out)>0:
                    self.writer.write(pickle.dumps(out))
                out = self.process()
        # We are done
        logger.debug("%s exiting..." % self.myName())
        self.closeImage(self.line, self.height, self.height // 2)

    def process(self):
        # No result yet
        out = None

        try:
            # Parse bitmap file data (scanlines)
            if self.width>0:
                w = self.width * 3
                if len(self.data)>=w:
                    # Advance scanline
                    self.line = self.line + 1
                    # If running as a service...
                    if self.service:
                        # Write a scanline into open image file
                        self.writeFile(self.data[0:w])
                        # Close once the last scanline reached
                        if self.line>=self.height:
                            self.closeImage(self.line, self.height)
                        # Empty result
                        out = {}
                    else:
                        # Compose result
                        out = {
                            "mode":   "SSTV",
                            "pixels": base64.b64encode(self.data[0:w]).decode(),
                            "line":   self.line-1,
                            "width":  self.width,
                            "height": self.height
                        }
                    # If we reached the end of frame, finish scan
                    if self.line>=self.height:
                        self.width  = 0
                        self.height = 0
                        self.line   = 0
                        self.mode   = 0
                    # Remove parsed data
                    del self.data[0:w]

            else:
                # Search for the leading 'BM' or ' ['
                w = self.data.find(b'BM')
                d = self.data.find(b' [')
                # If not found...
                if w<0 and d<0:
                    # Skip all but last character (may have 'B')
                    del self.data[0:len(self.data)-1]
                elif w<0 or (d>=0 and d<w):
                    # Skip everything until ' ['
                    del self.data[0:d]
                    # Look for the closing bracket
                    w = self.data.find(b']')
                    if w>=0:
                        # Extract message contents
                        msg = self.data[2:w].decode()
                        # Remove parsed data
                        del self.data[0:w+1]
                        # Log message
                        logger.debug("%s says [%s]" % (self.myName(), msg))
                        # If running as a service...
                        if self.service:
                            # Empty result
                            out = {}
                        else:
                            # Compose result
                            out = {
                                "mode":      "SSTV",
                                "message":   msg,
                                "frequency": self.frequency
                            }
                else:
                    # Skip everything until 'BM'
                    del self.data[0:w]
                    # If got the entire header...
                    if len(self.data)>=54:
                        self.width  = self.data[18] + (self.data[19]<<8) + (self.data[20]<<16) + (self.data[21]<<24)
                        self.height = self.data[22] + (self.data[23]<<8) + (self.data[24]<<16) + (self.data[25]<<24)
                        # BMP height value is negative
                        self.height = 0x100000000 - self.height
                        # SSTV mode is passed via reserved area at offset 6
                        self.mode   = self.data[6]
                        self.line   = 0
                        # Find mode name and time
                        modeName  = modeNames.get(self.mode) if self.mode in modeNames else "Unknown Mode %d" % self.mode
                        timeStamp = datetime.utcnow().strftime("%H:%M:%S")
                        fileName  = Storage.makeFileName("SSTV-{0}", self.frequency)
                        logger.debug("%s receiving %dx%d %s frame as '%s'." % (
                            self.myName(), self.width, self.height,
                            modeName, fileName
                        ))
                        # If running as a service...
                        if self.service:
                            # Create a new image file and write BMP header
                            self.newFile(fileName + ".bmp")
                            self.writeFile(self.data[0:54])
                            # Empty result
                            out = {}
                        else:
                            # Compose result
                            out = {
                                "mode":      "SSTV",
                                "width":     self.width,
                                "height":    self.height,
                                "sstvMode":  modeName,
                                "timestamp": timeStamp,
                                "filename":  fileName,
                                "frequency": self.frequency
                            }
                        # Remove parsed data
                        del self.data[0:54]

        except Exception as exptn:
            logger.debug("%s: Exception parsing: %s" % (self.myName(), str(exptn)))

        # Return parsed result or None if no result yet
        return out

