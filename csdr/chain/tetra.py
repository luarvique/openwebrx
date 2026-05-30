from csdr.chain.demodulator import (
    BaseDemodulatorChain,
    FixedAudioRateChain,
    FixedIfSampleRateChain,
    DialFrequencyReceiver,
    MetaProvider,
)
from csdr.module.tetra import TetraDemodModule
from owrx.tetra import TetraParser
from pycsdr.modules import Agc, Writer
from pycsdr.types import Format
import logging

logger = logging.getLogger(__name__)

# IQ sample rate fed by OpenWebRX into the demodulator.
# 96 kHz gives 4× oversampling of a 25 kHz TETRA channel.
TETRA_IF_RATE = 96000

# tetradec outputs 8 kHz mono 16-bit PCM.
TETRA_AUDIO_RATE = 8000


class TetraDemodulator(
    BaseDemodulatorChain,
    FixedIfSampleRateChain,
    FixedAudioRateChain,
    DialFrequencyReceiver,
    MetaProvider,
):
    """
    OpenWebRX demodulator for TETRA (TErrestrial Trunked RAdio).

    Produces decoded voice audio at 8 kHz for the client AND streams TETRA
    network metadata (MCC, MNC, BCC, SSI, TX frequency, …) to the panel.

    Voice is only audible on unencrypted TETRA calls. If the network uses
    air-interface encryption (Air-encr in metadata) the audio will be silent.
    """

    def __init__(self):
        self._demodModule  = TetraDemodModule(sampleRate=TETRA_IF_RATE)
        self._metaParser   = None
        self._dialFreq     = None

        agc = Agc(Format.SHORT)
        agc.setMaxGain(30)
        agc.setInitialGain(3)

        super().__init__([self._demodModule, agc])

    def getFixedIfSampleRate(self) -> int:
        return TETRA_IF_RATE

    def getFixedAudioRate(self) -> int:
        return TETRA_AUDIO_RATE

    def supportsSquelch(self) -> bool:
        return False

    def setMetaWriter(self, writer: Writer) -> None:
        if self._metaParser is None:
            self._metaParser = TetraParser()
            # Connect the parser to the text side-channel of the demod module.
            self._metaParser.setReader(self._demodModule.getTextReader())
            if self._dialFreq is not None:
                self._metaParser.setDialFrequency(self._dialFreq)
        self._metaParser.setWriter(writer)

    def setDialFrequency(self, frequency: int) -> None:
        self._dialFreq = frequency
        if self._metaParser is not None:
            self._metaParser.setDialFrequency(frequency)

    def stop(self):
        if self._metaParser is not None:
            self._metaParser.stop()
        super().stop()

