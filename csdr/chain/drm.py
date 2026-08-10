from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver
from pycsdr.modules import Convert, Downmix, Writer
from pycsdr.types import Format
from csdr.module.drm import DrmModule
from owrx.monitor import SocketMonitor
from owrx.feature import FeatureDetector

import pickle
import logging

logger = logging.getLogger(__name__)

class Drm(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, MetaProvider, DialFrequencyReceiver):
    def __init__(self):
        self.metaWriter = None
        self.frequency = 0

        # Only Dream 2.2 has --status-socket option
        if FeatureDetector().is_available("dream-2-2"):
            # Monitor DRM decoder status
            socketPath = SocketMonitor.getNewPathName("dream_status")
            self.monitor = SocketMonitor(socketPath)
            self.monitor.add_callback(self._onDrmStatus)
            self.monitor.start()
        else:
            self.monitor = None
            socketPath = None

        self.drmModule = DrmModule(socketPath)
        workers = [
            Convert(Format.COMPLEX_FLOAT, Format.COMPLEX_SHORT),
            self.drmModule,
            Downmix(Format.SHORT),
        ]
        super().__init__(workers)

    def supportsSquelch(self) -> bool:
        return False

    def getFixedIfSampleRate(self) -> int:
        return 48000

    def getFixedAudioRate(self) -> int:
        return 48000

    def setMetaWriter(self, writer: Writer) -> None:
        self.metaWriter = writer

    def setDialFrequency(self, frequency: int) -> None:
        if frequency != self.frequency:
            self.frequency = frequency

    def stop(self):
        # Stop all components
        if self.monitor:
            self.monitor.stop()
        if self.drmModule:
            self.drmModule.stop()
        super().stop()

    def _onDrmStatus(self, status):
        # Forward DRM status via metadata writer
        if self.metaWriter:
            try:
                if "mode" in status:
                    status["drm_mode"] = status["mode"]
                status["mode"] = "DRM"
                self.metaWriter.write(pickle.dumps(status));
            except Exception as e:
                logger.error("DRM status error: {0}".format(e))

