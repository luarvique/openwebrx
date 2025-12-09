from csdr.chain.demodulator import ServiceDemodulator, DialFrequencyReceiver
from csdr.module.toolbox import Rtl433Module, MultimonModule, RedseaModule, CwSkimmerModule, RttySkimmerModule, LameModule
from pycsdr.modules import FmDemod, Convert, Agc, Squelch, RealPart, SnrSquelch
from pycsdr.types import Format
from owrx.toolbox import TextParser, PageParser, SelCallParser, EasParser, IsmParser, RdsParser, Mp3Recorder
from owrx.skimmer import CwSkimmerParser, RttySkimmerParser
from owrx.config import Config

import math
import logging

logger = logging.getLogger(__name__)


class IsmDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 250000, service: bool = False):
        self.sampleRate = sampleRate
        self.parser = IsmParser(service=service)
        workers = [
            Rtl433Module(self.sampleRate, jsonOutput = True),
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


class MultimonDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, decoders: list[str], parser, withSquelch: bool = False):
        self.sampleRate = 22050
        self.squelch = None
        self.parser = parser
        workers = [
            FmDemod(),
            Convert(Format.FLOAT, Format.SHORT),
            MultimonModule(decoders),
            self.parser,
        ]
        # If using squelch, insert Squelch() at the start
        if withSquelch:
            self.measurementsPerSec = 16
            self.readingsPerSec = 4
            blockLength  = int(self.sampleRate / self.measurementsPerSec)
            self.squelch = Squelch(Format.COMPLEX_FLOAT,
                length      = blockLength,
                decimation  = 5,
                hangLength  = 2 * blockLength,
                flushLength = 5 * blockLength,
                reportInterval = int(self.measurementsPerSec / self.readingsPerSec)
            )
            workers.insert(0, self.squelch)

        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return self.squelch != None

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)

    def _convertToLinear(self, db: float) -> float:
        return float(math.pow(10, db / 10))

    def setSquelchLevel(self, level: float) -> None:
        if self.squelch:
            self.squelch.setSquelchLevel(self._convertToLinear(level))


class PageDemodulator(MultimonDemodulator):
    def __init__(self, service: bool = False):
        super().__init__(
            ["FLEX", "POCSAG512", "POCSAG1200", "POCSAG2400"],
            PageParser(service=service),
            # Enabling squelch in background mode just to make sure
            # multimon-ng is fed data in large chunks (>=512 samples).
            # POCSAG mode will not work otherwise, due to some issue
            # in multimon-ng. In the interactive mode, similar effect
            # is achieved by the Squelch() module in the main chain.
            withSquelch = service
        )


class SelCallDemodulator(MultimonDemodulator):
    def __init__(self, service: bool = False):
        super().__init__(
            ["DTMF", "EEA", "EIA", "CCIR"],
            SelCallParser(service=service),
            withSquelch = True
        )


class EasDemodulator(MultimonDemodulator):
    def __init__(self, service: bool = False):
        super().__init__(
            ["EAS"],
            EasParser(service=service),
            withSquelch = True
        )


class ZveiDemodulator(MultimonDemodulator):
    def __init__(self, service: bool = False):
        super().__init__(
            ["ZVEI1", "ZVEI2", "ZVEI3", "DZVEI", "PZVEI"],
            SelCallParser(service=service),
            withSquelch = True
        )


class RdsDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 171000, rbds: bool = False):
        self.sampleRate = sampleRate
        self.parser = RdsParser()
        workers = [
            Convert(Format.FLOAT, Format.SHORT),
            RedseaModule(sampleRate, rbds),
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


class CwSkimmerDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 96000, charCount: int = 4, service: bool = False):
        self.sampleRate = sampleRate
        self.parser = CwSkimmerParser(service)
        workers = [
            RealPart(),
            CwSkimmerModule(sampleRate, charCount),
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


class RttySkimmerDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 96000, charCount: int = 4, service: bool = False):
        self.sampleRate = sampleRate
        self.parser = RttySkimmerParser(service)
        workers = [
            RealPart(),
            RttySkimmerModule(sampleRate, charCount),
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


class AudioRecorder(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 24000, service: bool = False):
        # Get settings
        pm = Config.get()
        squelchLevel = pm["rec_squelch"]
        hangTime = int(sampleRate * pm["rec_hang_time"] / 1000)
        produceSilence = pm["rec_produce_silence"]
        # Initialize state
        self.sampleRate = sampleRate
        self.recorder = Mp3Recorder(service)
        self.squelch = SnrSquelch(Format.FLOAT, 2048, 512, hangTime, 0, 1, produceSilence)
        # Set recording squelch level
        self.setSquelchLevel(squelchLevel)
        workers = [
            self.squelch,
            Convert(Format.FLOAT, Format.SHORT),
            LameModule(sampleRate),
            self.recorder,
        ]
        # Connect all the workers
        super().__init__(workers)

    def _convertToLinear(self, db: float) -> float:
        return float(math.pow(10, db / 10))

    def setSquelchLevel(self, level: float) -> None:
        self.squelch.setSquelchLevel(self._convertToLinear(level))

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return True

    def setDialFrequency(self, frequency: int) -> None:
        # Not restarting LAME, it is ok to continue on a new file
        self.recorder.setDialFrequency(frequency)
