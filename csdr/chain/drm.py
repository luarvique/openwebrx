from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain
from pycsdr.modules import Convert, Downmix
from pycsdr.types import Format
from csdr.module.drm import DrmModule
from owrx.drm import DrmStatusMonitor

import pickle
import logging
import threading

logger = logging.getLogger(__name__)

class Drm(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain):
    def __init__(self):
        self.drm_module = DrmModule()
        workers = [
            Convert(Format.COMPLEX_FLOAT, Format.COMPLEX_SHORT),
            self.drm_module,
            Downmix(Format.SHORT),
        ]
        super().__init__(workers)

        # Monitor DRM decoder status
        self.monitor = DrmStatusMonitor(self.drm_module.getSocketPath())
        self.monitor.add_callback(self._on_drm_status)
        self.monitor.start()
        logger.debug(f"DRM chain ready: {self.drm_module.getSocketPath()}")

        self.metawriter = None
        self.metawriter_lock = threading.Lock()

    def supportsSquelch(self) -> bool:
        return False

    def getFixedIfSampleRate(self) -> int:
        return 48000

    def getFixedAudioRate(self) -> int:
        return 48000

    def setMetaWriter(self, writer: Writer) -> None:
        with self.metawriter_lock:
            self.metawriter = writer

    def stop(self):
        # Stop all components
        if self.monitor:
            self.monitor.stop()
        if self.drm_module:
            self.drm_module.stop()
        super().stop()

    def _on_drm_status(self, status):
        # Forward DRM status via metadata writer
        with self.metawriter_lock:
            if self.metawriter:
                try:
                    msg = { "type": "drm_status", "value": status }
                    self.metawriter.write(pickle.dumps(msg))
                except Exception as e:
                    logger.error(f"DRM status error: {e}")
