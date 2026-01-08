from pycsdr.modules import ExecModule
from pycsdr.types import Format


class SondeModule(ExecModule):
    def __init__(self, type: str = "rs41mod", sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False, options = []):
        cmd = [ type, "-", str(sampleRate), "32" ] + options
        if iq:
            cmd += [ "--IQ", "0" ]
        if jsonOutput:
            cmd += [ "--json"]
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd)


class Rs41Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False):
        super().__init__("rs41mod", sampleRate, iq, jsonOutput)


class Dfm9Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False):
        super().__init__("dfm09mod", sampleRate, iq, jsonOutput)


class Dfm17Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False):
        super().__init__("dfm09mod", sampleRate, iq, jsonOutput, ["-v", "-i"])


class M10Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False):
        super().__init__("m10mod", sampleRate, iq, jsonOutput)


class M20Module(SondeModule):
    def __init__(self, sampleRate: int = 48000, iq: bool = True, jsonOutput: bool = False):
        super().__init__("m20mod", sampleRate, iq, jsonOutput)

