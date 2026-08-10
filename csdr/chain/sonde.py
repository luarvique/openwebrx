from csdr.chain.demodulator import ServiceDemodulator, DialFrequencyReceiver
from csdr.module.sonde import Mts01Module, Rs41Module, Dfm9Module, Dfm17Module, M10Module, M20Module
from owrx.sonde import SondeParser


class SondeDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, module, sampleRate: int = 48000, service: bool = False):
        self.sampleRate = sampleRate
        self.parser = SondeParser(service)
        workers = [ module, self.parser ]
        super().__init__(workers)

    def supportsSquelch(self) -> bool:
        return False

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class Mts01Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 48000, service: bool = False):
        module = Mts01Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)


class Rs41Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 48000, service: bool = False):
        module = Rs41Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)


class Dfm9Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 48000, service: bool = False):
        module = Dfm9Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)


class Dfm17Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 48000, service: bool = False):
        module = Dfm17Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)


class M10Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 76800, service: bool = False):
        module = M10Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)


class M20Demodulator(SondeDemodulator):
    def __init__(self, sampleRate: int = 76800, service: bool = False):
        module = M20Module(sampleRate, jsonOutput = True)
        super().__init__(module, sampleRate, service)
