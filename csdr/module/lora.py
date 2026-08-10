from pycsdr.types import Format
from csdr.module import PopenModule


class LoraModule(PopenModule):
    def __init__(self, sampleRate: int = 1000000, jsonOutput: bool = False, options=[]):
        self.cmd = [
            "lorarx", "-i", "/dev/stdin", "-r", str(sampleRate),
            "-f", "f32", "-v", "-N", "-Q"
        ] + options
        if jsonOutput:
            self.cmd += [ "-j", "/dev/stdout" ]
        super().__init__()

    def getCommand(self):
        return self.cmd

    def getInputFormat(self) -> Format:
        return Format.COMPLEX_FLOAT

    def getOutputFormat(self) -> Format:
        return Format.CHAR
