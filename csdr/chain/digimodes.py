from csdr.chain.demodulator import ServiceDemodulator, SecondaryDemodulator, DialFrequencyReceiver, SecondarySelectorChain
from csdr.module.msk144 import Msk144Module, ParserAdapter
from owrx.audio.chopper import AudioChopper, AudioChopperParser
from owrx.aprs.kiss import KissDeframer
from owrx.aprs import Ax25Parser, AprsParser
from pycsdr.modules import Convert, FmDemod, Agc, TimingRecovery, DBPskDecoder, VaricodeDecoder, RttyDecoder, BaudotDecoder, Lowpass, MFRttyDecoder, CwDecoder, SstvDecoder, FaxDecoder, SitorBDecoder, Ccir476Decoder, DscDecoder, Ccir493Decoder, NavtexDecoder, Shift
from pycsdr.types import Format
from owrx.aprs.direwolf import DirewolfModule
from owrx.sstv import SstvParser
from owrx.fax import FaxParser
from owrx.marine import DscParser, NavtexParser
from owrx.config import Config
from owrx.toolbox import SondeZilogParser
from csdr.module.toolbox import SondeZilogModule


class AudioChopperDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, mode: str, parser: AudioChopperParser):
        self.chopper = AudioChopper(mode, parser)
        workers = [Convert(Format.FLOAT, Format.SHORT), self.chopper]
        super().__init__(workers)

    def getFixedAudioRate(self):
        return 12000

    def setDialFrequency(self, frequency: int) -> None:
        self.chopper.setDialFrequency(frequency)


class Msk144Demodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self):
        self.parser = ParserAdapter()
        workers = [
            Convert(Format.FLOAT, Format.SHORT),
            Msk144Module(),
            self.parser,
        ]
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return 12000

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class PacketDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False, ais: bool = False):
        self.parser = AprsParser()
        workers = [
            FmDemod(),
            Convert(Format.FLOAT, Format.SHORT),
            DirewolfModule(service=service, ais=ais),
            KissDeframer(),
            Ax25Parser(),
            self.parser,
        ]
        super().__init__(workers)

    def supportsSquelch(self) -> bool:
        return False

    def getFixedAudioRate(self) -> int:
        return 48000

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


# Zilog RS tools:
# They take 48kbps 32bit float I/Q input directly (with --iq and --IQ options)...
class SondeDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False, sondetype: str = "rs41", iq: bool = True):
        self.parser = SondeZilogParser()
        workers = [
            SondeZilogModule(sondetype = sondetype, iq = iq),
            self.parser,
        ]
        super().__init__(workers)

    def supportsSquelch(self) -> bool:
        return False

    def getFixedAudioRate(self) -> int:
        return 48000

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class PskDemodulator(SecondaryDemodulator, SecondarySelectorChain):
    def __init__(self, baudRate: float):
        self.baudRate = baudRate
        # this is an assumption, we will adjust in setSampleRate
        self.sampleRate = 12000
        secondary_samples_per_bits = int(round(self.sampleRate / self.baudRate)) & ~3
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            TimingRecovery(Format.COMPLEX_FLOAT, secondary_samples_per_bits, 0.5, 2),
            DBPskDecoder(),
            VaricodeDecoder(),
        ]
        super().__init__(workers)

    def getBandwidth(self):
        return self.baudRate

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        secondary_samples_per_bits = int(round(self.sampleRate / self.baudRate)) & ~3
        self.replace(1, TimingRecovery(Format.COMPLEX_FLOAT, secondary_samples_per_bits, 0.5, 2))


class RttyDemodulator(SecondaryDemodulator, SecondarySelectorChain):
    def __init__(self, baudRate, bandWidth, invert=False):
        self.baudRate = baudRate
        self.bandWidth = bandWidth
        self.invert = invert
        # this is an assumption, we will adjust in setSampleRate
        self.sampleRate = 12000
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            FmDemod(),
            Lowpass(Format.FLOAT, cutoff),
            TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10),
            RttyDecoder(invert),
            BaudotDecoder(),
        ]
        super().__init__(workers)

    def getBandwidth(self) -> float:
        return self.bandWidth

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        self.replace(2, Lowpass(Format.FLOAT, cutoff))
        self.replace(3, TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10))


class CwDemodulator(SecondaryDemodulator, SecondarySelectorChain, DialFrequencyReceiver):
    def __init__(self, bandWidth: float = 100):
        pm = Config.get()
        self.sampleRate = 12000
        self.bandWidth = bandWidth
        self.showCw = pm["cw_showcw"]
        self.decoder = CwDecoder(self.sampleRate, self.showCw)
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            self.decoder
        ]
        super().__init__(workers)

    def getBandwidth(self):
        return self.bandWidth

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        self.decoder = CwDecoder(sampleRate, self.showCw)
        self.replace(1, self.decoder)

    def setDialFrequency(self, frequency: int) -> None:
        self.decoder.reset()


class MFRttyDemodulator(SecondaryDemodulator, SecondarySelectorChain):
    def __init__(self, targetWidth: float, baudRate: float, reverse: bool):
        self.sampleRate = 12000
        self.offset = 550
        self.targetWidth = targetWidth
        self.baudRate = baudRate
        self.reverse = reverse
        workers = [
            Shift((self.targetWidth/2 + self.offset) / self.sampleRate),
            Agc(Format.COMPLEX_FLOAT),
            MFRttyDecoder(self.sampleRate, self.offset, int(self.targetWidth), self.baudRate, self.reverse),
        ]
        super().__init__(workers)

    def getBandwidth(self):
        return self.targetWidth + 100.0

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        self.replace(0, Shift((self.targetWidth/2 + self.offset) / sampleRate))
        self.replace(2, MFRttyDecoder(sampleRate, self.offset, int(self.targetWidth), self.baudRate, self.reverse))


class SstvDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False):
        self.parser = SstvParser(service=service)
        self.sampleRate = 24000
        self.dbgTime = 300000
        workers = [
            SstvDecoder(self.sampleRate, self.dbgTime),
            self.parser
        ]
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class FaxDemodulator(ServiceDemodulator, DialFrequencyReceiver):
    def __init__(self, service: bool = False):
        pm = Config.get()
        self.parser      = FaxParser(service=service)
        self.sampleRate  = 12000
        self.lpm         = pm["fax_lpm"]
        self.length      = pm["fax_max_length"]
        self.dbgTime     = 300000
        self.postProcess = pm["fax_postprocess"]
        self.color       = pm["fax_color"]
        self.am          = pm["fax_am"]
        workers = [
            FaxDecoder(
                self.sampleRate,
                self.lpm,
                self.length,
                self.dbgTime,
                postProcess = self.postProcess,
                color = self.color,
                am = self.am
            ),
            self.parser
        ]
        super().__init__(workers)

    def getFixedAudioRate(self) -> int:
        return self.sampleRate

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)


class SitorBDemodulator(SecondaryDemodulator, SecondarySelectorChain):
    def __init__(self, baudRate=100, bandWidth=170, invert=False):
        self.baudRate  = baudRate
        self.bandWidth = bandWidth
        # this is an assumption, we will adjust in setSampleRate
        self.sampleRate = self.bandWidth * 10 #12000
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            FmDemod(),
            Lowpass(Format.FLOAT, cutoff),
            TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10),
            SitorBDecoder(invert=invert),
            Ccir476Decoder(),
        ]
        super().__init__(workers)

    def getBandwidth(self) -> float:
        return self.bandWidth

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        self.replace(2, Lowpass(Format.FLOAT, cutoff))
        self.replace(3, TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10))


class DscDemodulator(SecondaryDemodulator, SecondarySelectorChain, DialFrequencyReceiver):
    def __init__(self, baudRate=100, bandWidth=170, invert=False, service=False):
        self.baudRate  = baudRate
        self.bandWidth = bandWidth
        self.parser    = DscParser(service=service)
        # this is an assumption, we will adjust in setSampleRate
        self.sampleRate = self.bandWidth * 10 #12000
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            FmDemod(),
            Lowpass(Format.FLOAT, cutoff),
            TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10),
            Ccir493Decoder(invert=invert),
            DscDecoder(),
            self.parser
        ]
        super().__init__(workers)

    def getBandwidth(self) -> float:
        return self.bandWidth

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        self.replace(2, Lowpass(Format.FLOAT, cutoff))
        self.replace(3, TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10))

    # DialFrequencyReceiver
    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)

    # ServiceDemodulator
    def getFixedAudioRate(self):
        return self.sampleRate


class NavtexDemodulator(SecondaryDemodulator, SecondarySelectorChain, DialFrequencyReceiver):
    def __init__(self, baudRate=100, bandWidth=170, invert=False, service=False):
        self.baudRate  = baudRate
        self.bandWidth = bandWidth
        self.parser    = NavtexParser(service=service)
        # this is an assumption, we will adjust in setSampleRate
        self.sampleRate = self.bandWidth * 10 #12000
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        workers = [
            Agc(Format.COMPLEX_FLOAT),
            FmDemod(),
            Lowpass(Format.FLOAT, cutoff),
            TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10),
            SitorBDecoder(invert=invert),
            Ccir476Decoder(),
            NavtexDecoder(),
            self.parser
        ]
        super().__init__(workers)

    def getBandwidth(self) -> float:
        return self.bandWidth

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        secondary_samples_per_bit = int(round(self.sampleRate / self.baudRate))
        cutoff = self.baudRate / self.sampleRate
        loop_gain = self.sampleRate / self.getBandwidth() / 5
        self.replace(2, Lowpass(Format.FLOAT, cutoff))
        self.replace(3, TimingRecovery(Format.FLOAT, secondary_samples_per_bit, loop_gain, 10))

    # DialFrequencyReceiver
    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)

    # ServiceDemodulator
    def getFixedAudioRate(self):
        return self.sampleRate
