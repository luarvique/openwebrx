from csdr.chain.demodulator import ServiceDemodulator, DialFrequencyReceiver
from csdr.module.lora import LoraModule
from pycsdr.types import Format
from owrx.lora import LoraParser

import logging

logger = logging.getLogger(__name__)


class LoraDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, sampleRate: int = 1000000, options = []):
        self.sampleRate = sampleRate
        self.parser = LoraParser()
        workers = [
            LoraModule(sampleRate, jsonOutput = True, options = options),
            self.parser,
        ]
        # Connect all the workers
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def supportsSquelch(self) -> bool:
        return True

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class LoraWanDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-b", "7",
            "-s", "12", "-s", "11", "-s", "10", "-s", "9", "-s", "8",
            "-s", "7", "-s", "-12", "-s", "-11", "-s", "-10",
            "-s", "-9", "-s", "-8", "-s", "-7"
        ])


class LoraAprsDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", "7", "-s", "9", "-s", "12"
        ])


class LoraFanetDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-b", "8", "-s", "7"
        ])


class MeshtasticDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", "8", "-s", "7", "-s", "8",
            "-s", "9", "-s", "10", "-s", "11"
        ])


class MeshcoreDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "5", "-W", "50", "-b", "6", "-s", "7", "-s", "8"
        ])


class MeshComDemodulator(LoraDemodulator):
    def __init__(self, sampleRate: int = 1000000, service: bool = False):
        super().__init__(sampleRate, [
            "-H", "1", "-W", "50", "-b", "8", "-s", "10", "-s", "11"
        ])
