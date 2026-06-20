from csdr.chain.demodulator import ServiceDemodulator, DialFrequencyReceiver
from csdr.module.lora import LoraModule
from pycsdr.types import Format
from owrx.lora import LoraParser
from owrx.meshtastic import MeshtasticParser
from owrx.config import Config

import logging

logger = logging.getLogger(__name__)


class LoraDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 1000000, options = [], parser = None):
        self.sampleRate = sampleRate
        self.parser = parser
        workers = [
            LoraModule(sampleRate, jsonOutput = True, options = options),
        ]
        if self.parser is not None:
            workers += [ self.parser ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return True

    def setDialFrequency(self, frequency: int) -> None:
        if self.parser is not None:
            self.parser.setDialFrequency(frequency)


class LoraWanDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        pm = Config().get()
        bw = pm["lorawan_bw"]
        super().__init__(sampleRate, [
            "-H", "5", "-b", str(bw),
            "-s", "12", "-s", "11", "-s", "10", "-s", "9", "-s", "8",
            "-s", "7", "-s", "-12", "-s", "-11", "-s", "-10",
            "-s", "-9", "-s", "-8", "-s", "-7"
        ], LoraParser(service))


class LoraAprsDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", "7", "-s", "9", "-s", "12"
        ], LoraParser(service))


class LoraFanetDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-b", "8", "-s", "7"
        ], LoraParser(service))


class MeshtasticDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        pm = Config().get()
        bw = pm["meshtastic_bw"]
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", str(bw), "-s", "7", "-s", "8",
            "-s", "9", "-s", "10", "-s", "11"
        ], MeshtasticParser(service))


class MeshcoreDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        pm = Config().get()
        bw = pm["meshcore_bw"]
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", str(bw), "-s", "7", "-s", "8"
        ], LoraParser(service))


class MeshComDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        pm = Config().get()
        bw = pm["meshcom_bw"]
        super().__init__(sampleRate, [
            "-H", "1", "-W", "50", "-b", str(bw), "-s", "10", "-s", "11"
        ], LoraParser(service))
