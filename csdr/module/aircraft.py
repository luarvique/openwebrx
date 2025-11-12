from pycsdr.modules import ExecModule
from pycsdr.types import Format
from owrx.config import Config

import os


class DumpHfdlModule(ExecModule):
    def __init__(self, sampleRate: int = 12000, jsonOutput: bool = False):
        cmd = [
            "dumphfdl", "--iq-file", "-", "--sample-format", "CF32",
            "--sample-rate", str(sampleRate), "--output",
            "decoded:%s:file:path=-" % ("json" if jsonOutput else "text"),
            "--utc", "--centerfreq", "0", "0"
        ]
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd)


class DumpVdl2Module(ExecModule):
    def __init__(self, sampleRate: int = 105000, jsonOutput: bool = False):
        cmd = [
            "dumpvdl2", "--iq-file", "-", "--sample-format", "S16_LE",
            "--oversample", str(sampleRate // 105000), "--output",
            "decoded:%s:file:path=-" % ("json" if jsonOutput else "text"),
            "--decode-fragments", "--utc"
        ]
        super().__init__(Format.COMPLEX_SHORT, Format.CHAR, cmd)


class Dump1090Module(ExecModule):
    def __init__(self, rawOutput: bool = False, jsonFolder: str = None):
        pm  = Config.get()
        lat = pm["receiver_gps"]["lat"]
        lon = pm["receiver_gps"]["lon"]
        cmd = [
            "dump1090", "--ifile", "-", "--iformat", "SC16",
            "--lat", str(lat), "--lon", str(lon),
            "--modeac", "--metric"
        ]
        # If JSON files folder supplied, use that, disable STDOUT output
        if jsonFolder is not None:
            try:
                os.makedirs(jsonFolder, exist_ok = True)
                cmd += [ "--quiet", "--write-json", jsonFolder ]
            except:
                self.jsonFolder = None
                pass
        # RAW STDOUT output only makes sense if we are not using JSON
        if rawOutput and jsonFolder is None:
            cmd += [ "--raw" ]
        super().__init__(Format.COMPLEX_SHORT, Format.CHAR, cmd)


class Dump978Module(ExecModule):
    def __init__(self, jsonOutput: bool = False):
        cmd = [
            "dump978-fa", "--stdin", "--format", "CF32H"
        ]
        # Choose between JSON and RAW output
        if jsonOutput:
            cmd += [ "--json-stdout" ]
        else:
            cmd += [ "--raw-stdout" ]
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd)


class AcarsDecModule(ExecModule):
    def __init__(self, sampleRate: int = 12000, jsonOutput: bool = False):
        self.sampleRate = sampleRate
        self.jsonOutput = jsonOutput
        cmd = [
            "acarsdec", "--sndfile", "/dev/stdin,subtype=6",
            "--output", str("json:file" if self.jsonOutput else "full:file")
        ]
        super().__init__(Format.FLOAT, Format.CHAR, cmd)

