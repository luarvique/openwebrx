from csdr.chain.demodulator import ServiceDemodulator, DialFrequencyReceiver
from csdr.module.aircraft import DumpHfdlModule, DumpVdl2Module, Dump1090Module, Dump978Module, AcarsDecModule
from owrx.aircraft import HfdlParser, Vdl2Parser, AdsbParser, AcarsParser, UatParser
from pycsdr.modules import Convert, Agc
from pycsdr.types import Format

import os
import logging

logger = logging.getLogger(__name__)


class HfdlDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False):
        self.sampleRate = 12000
        self.parser = HfdlParser(service=service)
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            DumpHfdlModule(self.sampleRate, jsonOutput = True),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return False

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class Vdl2Demodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False):
        self.sampleRate = 105000
        self.parser = Vdl2Parser(service=service)
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            Convert(Format.COMPLEX_FLOAT, Format.COMPLEX_SHORT),
            DumpVdl2Module(self.sampleRate, jsonOutput = True),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return False

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class AdsbDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False, jsonFile: str = "/tmp/dump1090/aircraft.json"):
        self.sampleRate = 2400000
        self.parser = AdsbParser(service=service, jsonFile=jsonFile)
        jsonFolder = os.path.dirname(jsonFile) if jsonFile else None
        workers = [
            Convert(Format.COMPLEX_FLOAT, Format.COMPLEX_SHORT),
            Dump1090Module(rawOutput = True, jsonFolder = jsonFolder),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return False

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class UatDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False, jsonFile: str = "/tmp/dump978/aircraft.json"):
        self.sampleRate = 2083334
        self.parser = UatParser(service=service)
        workers = [
            Dump978Module(jsonOutput = True),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return False

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class AcarsDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False):
        self.sampleRate = 12000
        self.parser = AcarsParser(service=service)
        workers = [
            AcarsDecModule(self.sampleRate, jsonOutput = True),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return False

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)

