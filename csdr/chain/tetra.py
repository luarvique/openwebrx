from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver
from pycsdr.modules import Agc, Writer
from pycsdr.types import Format
from csdr.module.tetra import TetraModule
from owrx.monitor import FileMonitor
from owrx.tetra import TetraParser

import pickle
import logging
import os

logger = logging.getLogger(__name__)

class Tetra(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver):
    def __init__(self):
        filePath = FileMonitor.getNewPathName("tetra")
        os.mkfifo(filePath)

        self.metaWriter = None
        self.sampleRate = 96000
        self.tetraModule = TetraModule(self.sampleRate, filePath)
        self.parser = TetraParser()

        self.monitor = FileMonitor(filePath)
        self.monitor.add_callback(self._onTetraStatus)
        self.monitor.start()

        agc = Agc(Format.SHORT)
        agc.setMaxGain(30)
        agc.setInitialGain(3)

        workers = [
            self.tetraModule,
            agc,
        ]
        super().__init__(workers)


    def supportsSquelch(self) -> bool:
        return False

    def getFixedIfSampleRate(self) -> int:
        return self.sampleRate

    def getFixedAudioRate(self) -> int:
        return 8000

    def setMetaWriter(self, writer: Writer) -> None:
        self.metaWriter = writer

    def setDialFrequency(self, frequency: int) -> None:
        self.parser.setDialFrequency(frequency)

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
                status = self.parser.parse(status)
                if status:
                    self.metaWriter.write(pickle.dumps(status));
            except Exception as e:
                logger.error("Tetra status error: %s", e)

