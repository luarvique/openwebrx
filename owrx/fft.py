from owrx.config import Config
from csdr.chain.fft import FftChain
from owrx.source import SdrSourceEventClient, SdrSourceState, SdrClientClass
from owrx.noisefloor import AdaptiveNoiseFloorEstimator
from owrx.property import PropertyStack
from pycsdr.modules import Buffer
import numpy as np
import threading
import time

import logging

logger = logging.getLogger(__name__)

# How often the estimated squelch level is published to sdrSource props (Hz).
_NOISE_PUBLISH_HZ = 1.0
# FPS of the dedicated noise-floor FFT chain (cheap — just needs a slow trend).
_NOISE_FFT_FPS = 2


class SpectrumThread(SdrSourceEventClient):
    def __init__(self, sdrSource):
        self.sdrSource = sdrSource
        super().__init__()

        stack = PropertyStack()
        stack.addLayer(0, self.sdrSource.props)
        stack.addLayer(1, Config.get())
        self.props = stack.filter(
            "samp_rate",
            "fft_size",
            "fft_fps",
            "fft_voverlap_factor",
            "fft_compression",
        )

        self.dsp = None
        self.reader = None

        # Noise-floor estimation (separate low-FPS chain, no compression)
        self._noise_dsp = None
        self._noise_reader = None
        self._noise_estimator = None
        self._noise_thread = None
        self._noise_stop = threading.Event()

        self.subscriptions = []

        logger.debug("Spectrum thread initialized successfully.")

    def start(self):
        if self.dsp is not None:
            return

        self.dsp = FftChain(
            self.props['samp_rate'],
            self.props['fft_size'],
            self.props['fft_voverlap_factor'],
            self.props['fft_fps'],
            self.props['fft_compression']
        )
        self.sdrSource.addClient(self)

        self.subscriptions += [
            self.props.filter("fft_size").wire(self.restart),
            # these props can be set on the fly
            self.props.wireProperty("samp_rate", self.dsp.setSampleRate),
            self.props.wireProperty("fft_fps", self.dsp.setFps),
            self.props.wireProperty("fft_voverlap_factor", self.dsp.setVOverlapFactor),
            self.props.wireProperty("fft_compression", self._setCompression),
        ]

        if self.sdrSource.isAvailable():
            self.dsp.setReader(self.sdrSource.getBuffer().getReader())
            self._startNoiseEstimator()

    def _setCompression(self, compression):
        if self.reader:
            self.reader.stop()
        try:
            self.dsp.setCompression(compression)
        except ValueError:
            # expected since the compressions have different formats
            pass

        buffer = Buffer(self.dsp.getOutputFormat())
        self.dsp.setWriter(buffer)
        self.reader = buffer.getReader()
        threading.Thread(target=self.dsp.pump(self.reader.read, self.sdrSource.writeSpectrumData)).start()

    # ------------------------------------------------------------------
    # Noise-floor estimation
    # ------------------------------------------------------------------

    def _startNoiseEstimator(self):
        """Spin up a dedicated low-FPS FFT chain (uncompressed) that feeds
        the AdaptiveNoiseFloorEstimator. Runs in a daemon thread so it
        doesn't block shutdown."""
        self._stopNoiseEstimator()

        fft_size = self.props['fft_size']
        samp_rate = self.props['samp_rate']

        try:
            self._noise_dsp = FftChain(
                samp_rate,
                fft_size,
                0,               # no overlap (cheap)
                _NOISE_FFT_FPS,
                "none",          # uncompressed float32 — we need real values
            )
            self._noise_dsp.setReader(self.sdrSource.getBuffer().getReader())

            noise_buf = Buffer(self._noise_dsp.getOutputFormat())
            self._noise_dsp.setWriter(noise_buf)
            self._noise_reader = noise_buf.getReader()

            cfg = Config.get()
            margin = cfg["squelch_auto_margin"] if "squelch_auto_margin" in cfg else 10
            self._noise_estimator = AdaptiveNoiseFloorEstimator(
                fft_size=fft_size,
                samp_rate=samp_rate,
                margin_db=margin,
            )

            self._noise_stop.clear()
            self._noise_thread = threading.Thread(
                target=self._noise_loop,
                daemon=True,
                name="noise_floor_estimator",
            )
            self._noise_thread.start()
            logger.debug("Noise-floor estimator started (fft_size=%d, samp_rate=%d)", fft_size, samp_rate)
        except Exception:
            logger.exception("Failed to start noise-floor estimator")
            self._stopNoiseEstimator()

    def _noise_loop(self):
        """Read uncompressed FFT frames, update the estimator, publish throttled."""
        last_publish = 0.0
        publish_interval = 1.0 / _NOISE_PUBLISH_HZ

        while not self._noise_stop.is_set():
            try:
                data = self._noise_reader.read()
            except Exception:
                break

            if data is None or len(data) == 0:
                break

            try:
                spectrum_db = np.frombuffer(data, dtype=np.float32)
            except Exception:
                continue

            if len(spectrum_db) != self._noise_estimator._fft_size:
                continue

            self._noise_estimator.update(spectrum_db)

            now = time.monotonic()
            if now - last_publish >= publish_interval:
                self._publishNoiseFloor()
                last_publish = now

    def _publishNoiseFloor(self):
        """Write the current adaptive squelch estimate to sdrSource props so
        DspManager can subscribe and apply it to the demodulator chain."""
        if self._noise_estimator is None:
            return
        # offset_freq=0: estimate at the SDR center bin (broadband estimate).
        # DspManager will pass the actual offset when it applies the level.
        level = self._noise_estimator.get_squelch_level(offset_freq_hz=0.0)
        if level is None:
            return
        try:
            self.sdrSource.props["estimated_squelch_level"] = level
        except Exception:
            pass

    def getNoiseFloorEstimator(self):
        """Return the current AdaptiveNoiseFloorEstimator, or None if not running.
        DspManager uses this to query the level at a specific offset_freq."""
        return self._noise_estimator

    def _stopNoiseEstimator(self):
        self._noise_stop.set()
        if self._noise_reader is not None:
            try:
                self._noise_reader.stop()
            except Exception:
                pass
            self._noise_reader = None
        if self._noise_dsp is not None:
            try:
                self._noise_dsp.stop()
            except Exception:
                pass
            self._noise_dsp = None
        if self._noise_thread is not None:
            self._noise_thread.join(timeout=2.0)
            self._noise_thread = None
        self._noise_estimator = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stopDsp(self):
        self._stopNoiseEstimator()
        if self.dsp is not None:
            self.dsp.stop()
            self.dsp = None
        if self.reader is not None:
            self.reader.stop()
            self.reader = None

    def stop(self):
        self.stopDsp()
        self.sdrSource.removeClient(self)
        while self.subscriptions:
            self.subscriptions.pop().cancel()

    def restart(self, *args, **kwargs):
        self.stop()
        self.start()

    def getClientClass(self) -> SdrClientClass:
        return SdrClientClass.USER

    def onStateChange(self, state: SdrSourceState):
        if state is SdrSourceState.STOPPING:
            self.stopDsp()
        elif state == SdrSourceState.RUNNING:
            if self.dsp is None:
                self.start()
            else:
                self.dsp.setReader(self.sdrSource.getBuffer().getReader())
                self._startNoiseEstimator()

    def onFail(self):
        self.stopDsp()

    def onShutdown(self):
        self.stopDsp()
