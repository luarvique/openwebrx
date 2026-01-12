from pycsdr.modules import ExecModule
from pycsdr.types import Format


class SondeModule(ExecModule):
    def __init__(self, type: str = "rs41mod", sampleRate: int = 48000, jsonOutput: bool = False, options = []):
        cmd = [ type, "-", str(sampleRate), "32", "--IQ", "0" ] + options
        if jsonOutput:
            cmd += [ "--json"]
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd)


class Rs41Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, jsonOutput: bool = False):
        super().__init__("rs41mod", sampleRate, jsonOutput, ["--ptu2"])


class Dfm9Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, jsonOutput: bool = False):
        super().__init__("dfm09mod", sampleRate, jsonOutput, ["--ptu"])


class Dfm17Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, jsonOutput: bool = False):
        super().__init__("dfm09mod", sampleRate, jsonOutput, ["-i", "--ptu"])


class M10Module(SondeModule):
    def __init__(self, sampleRate: int = 76800, jsonOutput: bool = False):
        super().__init__("m10mod", sampleRate, jsonOutput, ["--ptu"])


class M20Module(SondeModule):
    def __init__(self, sampleRate: int = 76800, jsonOutput: bool = False):
        super().__init__("m20mod", sampleRate, jsonOutput, ["--ptu"])

