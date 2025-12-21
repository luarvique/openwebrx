from owrx.toolbox import TextParser
from owrx.reporting import ReportingEngine
from owrx.lookup import HamCallsign
from owrx.config import Config
from datetime import datetime
import re

import logging

logger = logging.getLogger(__name__)


class SkimmerParser(TextParser):
    def __init__(self, mode: str, service: bool = False):
        # Looking for 4+ character callsigns, since 3 character
        # ones are often decoding errors
        self.reLine = re.compile(r"^([0-9]+):(.+)$")
        self.reCqCall = re.compile(r"(.*CQ +([A-Z]{2,}) +([0-9A-Z]{4,})) .*")
        self.reDeCall = re.compile(r"(.*(DE|TEST|DX|CW|CWT|SST|MST|QRP|POTA|SOTA) +([0-9A-Z]{4,})) .*")
        self.reTuCall = re.compile(r"(.*TU +([0-9A-Z]{4,}) +([0-9A-Z]{4,})) .*")
        self.re2dCall = re.compile(r"(.* +([0-9A-Z]{4,}) +DE *([0-9A-Z]{4,})) .*")
        self.re2xCall = re.compile(r"(.* +([0-9A-Z]{4,}) +([0-9A-Z]{4,})) .*")
        self.mode = mode
        self.frequency = 0
        self.freqChanged = False
        self.signals = {}
        # Construct parent object
        super().__init__(service=service)

    def parse(self, msg: bytes):
        # Parse incoming messages by frequency
        msg = msg.decode("utf-8", "replace")
        r = self.reLine.match(msg)
        if r is not None:
            freq = int(r.group(1)) + self.frequency
            text = r.group(2)
            if len(text) > 0:
                # Look for and report callsigns
                self._reportCallsign(freq, text)
                # In interactive mode...
                if not self.service:
                    # Compose result
                    out = { "mode": self.mode, "text": text, "freq": freq }
                    # Report frequency changes
                    if self.freqChanged:
                        self.freqChanged = False
                        out["changed"] = True
                    # Return parsed result to the caller
                    return out
        # No result
        return None

    def _reportCallsign(self, freq: int, text: str) -> None:
        # No callsign yet
        callsign = None
        callee   = None
        country  = None
        # Append new text to whatever received at given frequency
        if freq in self.signals:
            text = self.signals[freq] + text
        # Match '<callsign1> DE <callsign2>'
        if country is None:
            r = self.re2dCall.match(text)
            if r is not None and r.group(2) != r.group(3):
                callee  = r.group(2)
                country = HamCallsign.getCountry(callee)
                if country is not None:
                    callsign = r.group(3)
                    country  = HamCallsign.getCountry(callsign)
        # Match 'TU <callsign1> <callsign2>'
        if country is None:
            r = self.reTuCall.match(text)
            if r is not None and r.group(2) != r.group(3):
                callee  = r.group(2)
                country = HamCallsign.getCountry(callee)
                if country is not None:
                    callsign = r.group(3)
                    country  = HamCallsign.getCountry(callsign)
        # Match '<callsign> <callsign>', but ignore signal reports
        if country is None:
            r = self.re2xCall.match(text)
            if r is not None and r.group(2) == r.group(3) and "NN" not in r.group(2):
                callsign = r.group(2)
                country  = HamCallsign.getCountry(callsign)
        # Match 'CQ <...> <callsign>'
        if country is None:
            r = self.reCqCall.match(text)
            if r is not None:
                callsign = r.group(3)
                country  = HamCallsign.getCountry(callsign)
        # Match 'DE|TEST|DX|CW|CWT|SST|MST|QRP|POTA|SOTA <callsign>'
        if country is None:
            r = self.reDeCall.match(text)
            if r is not None:
                callsign = r.group(3)
                country  = HamCallsign.getCountry(callsign)
        # If callsign not matched...
        if country is None:
            # Keep last 32 received characters
            self.signals[freq] = text[-32:]
        else:
            # Clear all received characters
            self.signals[freq] = ""
            # Report callsign
            out = {
                "mode"      : self.mode,
                "timestamp" : round(datetime.now().timestamp() * 1000),
                "freq"      : freq,
                "callsign"  : callsign,
                "msg"       : r.group(1)
            }
            if country[0]:
                out["ccode"] = country[0]
            if country[1]:
                out["country"] = country[1]
            if callee:
                out["callee"] = callee
            ReportingEngine.getSharedInstance().spot(out)

    def setDialFrequency(self, frequency: int) -> None:
        self.freqChanged = frequency != self.frequency
        super().setDialFrequency(frequency)


class CwSkimmerParser(SkimmerParser):
    def __init__(self, service: bool = False):
        # Construct parent object
        super().__init__("CW", service=service)


class RttySkimmerParser(SkimmerParser):
    def __init__(self, service: bool = False):
        # Construct parent object
        super().__init__("RTTY", service=service)

