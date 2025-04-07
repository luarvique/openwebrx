from pycsdr.modules import ExecModule
from pycsdr.types import Format
from csdr.module import PopenModule
from owrx.config import Config
import os

class Rtl433Module(ExecModule):
    def __init__(self, sampleRate: int = 250000, jsonOutput: bool = False):
        cmd = [
            "rtl_433", "-r", "cs16:-", "-s", str(sampleRate),
            "-M", "time:unix" if jsonOutput else "time:utc",
            "-F", "json" if jsonOutput else "kv",
            "-A",
        ]
        super().__init__(Format.COMPLEX_SHORT, Format.CHAR, cmd)


class MultimonModule(ExecModule):
    def __init__(self, decoders: list[str]):
        pm  = Config.get()
        cmd = ["multimon-ng", "-", "-v0", "-C", pm["paging_charset"], "-c"]
        for x in decoders:
            cmd += ["-a", x]
        super().__init__(Format.SHORT, Format.CHAR, cmd)


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


class WavFileModule(PopenModule):
    def getInputFormat(self) -> Format:
        return Format.SHORT

    def start(self):
        # Create process and pumps
        super().start()
        # Created simulated .WAV file header
        byteRate = (self.sampleRate * 16 * 1) >> 3
        header = bytearray(44)
        header[0:3]   = b"RIFF"
        header[4:7]   = bytes([36, 0xFF, 0xFF, 0xFF])
        header[8:11]  = b"WAVE"
        header[12:15] = b"fmt "
        header[16]    = 16       # Chunk size
        header[20]    = 1        # Format (PCM)
        header[22]    = 1        # Number of channels (1)
        header[24]    = self.sampleRate & 0xFF
        header[25]    = (self.sampleRate >> 8) & 0xFF
        header[26]    = (self.sampleRate >> 16) & 0xFF
        header[27]    = (self.sampleRate >> 24) & 0xFF
        header[28]    = byteRate & 0xFF
        header[29]    = (byteRate >> 8) & 0xFF
        header[30]    = (byteRate >> 16) & 0xFF
        header[31]    = (byteRate >> 24) & 0xFF
        header[32]    = 2       # Block alignment (2 bytes)
        header[34]    = 16      # Bits per sample (16)
        header[36:39] = b"data"
        header[40:43] = bytes([0, 0xFF, 0xFF, 0xFF])
        # Send .WAV file header to the process
        self.process.stdin.write(header)


class AcarsDecModule(WavFileModule):
    def __init__(self, sampleRate: int = 12500, jsonOutput: bool = False):
        self.sampleRate = sampleRate
        self.jsonOutput = jsonOutput
        super().__init__()

    def getCommand(self):
        return [
            "acarsdec", "-f", "/dev/stdin",
            "-o", str(4 if self.jsonOutput else 1)
        ]

    def getOutputFormat(self) -> Format:
        return Format.CHAR


class CwSkimmerModule(ExecModule):
    def __init__(self, sampleRate: int = 48000, charCount: int = 4):
        cmd = ["csdr-cwskimmer", "-i", "-r", str(sampleRate), "-n", str(charCount)]
        super().__init__(Format.SHORT, Format.CHAR, cmd)


class RedseaModule(ExecModule):
    def __init__(self, sampleRate: int = 171000, rbds: bool = False):
        cmd = [ "redsea", "--input", "mpx", "--samplerate", str(sampleRate) ]
        if rbds:
            cmd += ["--rbds"]
        super().__init__(Format.SHORT, Format.CHAR, cmd)


class DablinModule(ExecModule):
    def __init__(self):
        self.serviceId = 0
        super().__init__(
            Format.CHAR,
            Format.FLOAT,
            self._buildArgs()
        )

    def _buildArgs(self):
        return ["dablin", "-p", "-s", "{:#06x}".format(self.serviceId)]

    def setDabServiceId(self, serviceId: int) -> None:
        self.serviceId = serviceId
        self.setArgs(self._buildArgs())
        self.restart()


class LameModule(ExecModule):
    def __init__(self, sampleRate: int = 24000):
        cmd = [
            "lame", "-r", "-m", "m", "--signed", "--bitwidth", "16",
            "-s", str(sampleRate / 1000), "-", "-"
        ]
        super().__init__(Format.SHORT, Format.CHAR, cmd)


class SatDumpModule(ExecModule):
    def __init__(self, mode: str = "noaa_apt", sampleRate: int = 50000, frequency: int = 137100000, outFolder: str = "/tmp/satdump", options = None):
        # Make sure we have output folder
        try:
            os.makedirs(outFolder, exist_ok = True)
        except:
            outFolder = "/tmp"
        # Compose command line
        cmd = [
            "satdump", "live", mode, outFolder,
            "--source", "file", "--file_path", "/dev/stdin",
            "--samplerate", str(sampleRate),
            "--frequency", str(frequency),
            "--baseband_format", "f32",
# Not trying to decode actual imagery for now, leaving .CADU file instead
#            "--finish_processing",
        ]
        # Add pipeline-specific options
        if options:
            for key in options.keys():
                cmd.append("--" + key)
                cmd.append(str(options[key]))
        # Create parent object
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd, doNotKill=True)
