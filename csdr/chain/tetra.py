from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver
from pycsdr.modules import Agc, Writer
from pycsdr.types import Format
from csdr.module.tetra import TetraModule
from owrx.tetra import TetraMonitor

import pickle
import logging

logger = logging.getLogger(__name__)

class Tetra(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver):
    def __init__(self):
        self.metaWriter = None
        self.sampleRate = 96000
        self.tetraModule = TetraModule(self.sampleRate)
        agc = Agc(Format.SHORT)
        agc.setMaxGain(30)
        agc.setInitialGain(3)
        workers = [
            self.tetraModule,
            agc,
        ]
        super().__init__(workers)

        # Monitor Tetra decoder status
        socketPath = self.tetraModule.getSocketPath()
        if socketPath is None:
            self.monitor = None
        else:
            self.monitor = TetraMonitor(socketPath)
            self.monitor.add_callback(self._onTetraStatus)
            self.monitor.start()

    def supportsSquelch(self) -> bool:
        return False

    def getFixedIfSampleRate(self) -> int:
        return self.sampleRate

    def getFixedAudioRate(self) -> int:
        return 8000

    def setMetaWriter(self, writer: Writer) -> None:
        self.metaWriter = writer

    def setDialFrequency(self, frequency: int) -> None:
        if self.monitor:
            self.monitor.setDialFrequency(frequency)

    def stop(self):
        # Stop all components
        if self.monitor:
            self.monitor.stop()
        if self.tetraModule:
            self.tetraModule.stop()
        super().stop()

    def _onTetraStatus(self, status):
        # Forward Tetra status via metadata writer
        if self.metaWriter:
            try:
                status["mode"] = "TETRA"
                self.metaWriter.write(pickle.dumps(status));
            except Exception as e:
                logger.error("Tetra status error: {0}".format(e))

