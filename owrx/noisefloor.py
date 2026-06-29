"""Adaptive noise-floor estimator for per-channel relative squelch.

Ported from the MSI SDR scanner (scanner/dsp.py:noise_floor_trend) and
adapted for the OpenWebRX+ FFT pipeline. Consumes full-band power spectra
(dBFS float32 per bin) and produces a squelch level relative to the
estimated noise floor rather than an absolute dBFS threshold.

Algorithm:
  1. Divide the spectrum into n_chunks coarse chunks, ignoring outer
     edge_fraction of bins where the SDR's analog filter rolls off.
  2. Take the 25th percentile of each chunk (signal peaks don't bias it).
  3. Linearly interpolate across chunks → per-bin noise-floor curve.
  4. Clamp boundary values to the nearest inner chunk (handles roll-off).
  5. Apply exponential moving average across FFT frames for temporal stability.
  6. squelch_level = noise_curve[tuned_bin] + margin_db

Thread safety: update() and get_squelch_level() / get_noise_floor_curve() are
safe to call from different threads (SpectrumThread writes, DspManager reads).
"""

import threading
import numpy as np
from typing import Optional


class AdaptiveNoiseFloorEstimator:
    def __init__(
        self,
        fft_size: int,
        samp_rate: int,
        margin_db: float = 10.0,
        n_chunks: int = 12,
        edge_fraction: float = 0.10,
        smoothing: float = 0.15,
    ):
        """
        Args:
            fft_size:       Number of FFT bins (must match incoming spectrum).
            samp_rate:      SDR sample rate in Hz (maps frequency offset to bins).
            margin_db:      dB above the estimated noise floor to set squelch.
            n_chunks:       Coarse chunks for percentile fit.
            edge_fraction:  Fraction of bins at each edge to exclude from fit
                            (SDR analog filter roll-off artificially lowers noise
                            at band edges and would skew the estimate downward).
            smoothing:      EMA weight for new frames: 0 = ignore new data,
                            1 = no smoothing. Default 0.15 converges in ~20 frames.
        """
        self._fft_size = fft_size
        self._samp_rate = samp_rate
        self._margin_db = margin_db
        self._n_chunks = n_chunks
        self._edge_fraction = edge_fraction
        self._smoothing = smoothing

        self._lock = threading.Lock()
        self._noise_curve: Optional[np.ndarray] = None  # shape (fft_size,), dBFS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, spectrum_db: np.ndarray) -> None:
        """Feed one FFT frame (full-band dBFS float32 array, length fft_size).
        Updates the internal noise-floor estimate via EMA. Cheap enough to
        call on every spectrum frame from SpectrumThread.
        """
        if len(spectrum_db) != self._fft_size:
            return
        new_curve = self._noise_floor_trend(spectrum_db)
        with self._lock:
            if self._noise_curve is None:
                self._noise_curve = new_curve
            else:
                # Exponential moving average for temporal stability
                self._noise_curve = (
                    (1.0 - self._smoothing) * self._noise_curve
                    + self._smoothing * new_curve
                )

    def get_squelch_level(
        self,
        offset_freq_hz: float = 0.0,
        bandwidth_hz: float = 5000.0,
    ) -> Optional[float]:
        """Return adaptive squelch level (dBFS) for the given frequency offset.

        Args:
            offset_freq_hz: Frequency of the demodulator channel relative to
                            SDR center (positive = above center). 0 = center bin.
            bandwidth_hz:   Channel bandwidth to average over (uses the median
                            of the noise curve across the channel's bins).

        Returns:
            Squelch threshold in dBFS, or None if no estimate is available yet.
        """
        with self._lock:
            if self._noise_curve is None:
                return None
            curve = self._noise_curve.copy()

        bin_hz = self._samp_rate / self._fft_size
        center_bin = int(self._fft_size / 2 + offset_freq_hz / bin_hz)
        center_bin = int(np.clip(center_bin, 0, self._fft_size - 1))

        half_bw_bins = max(1, int(bandwidth_hz / bin_hz / 2))
        lo = max(0, center_bin - half_bw_bins)
        hi = min(self._fft_size, center_bin + half_bw_bins + 1)

        regional_noise = float(np.median(curve[lo:hi]))
        return regional_noise + self._margin_db

    def get_noise_floor_curve(self) -> Optional[np.ndarray]:
        """Return a copy of the current per-bin noise-floor curve (dBFS),
        or None if no frames have been processed yet."""
        with self._lock:
            if self._noise_curve is None:
                return None
            return self._noise_curve.copy()

    def reset(self) -> None:
        """Clear the noise-floor history. Call on SDR center-frequency change
        so the estimator doesn't carry over stale data from a previous band."""
        with self._lock:
            self._noise_curve = None

    @property
    def margin_db(self) -> float:
        return self._margin_db

    @margin_db.setter
    def margin_db(self, value: float) -> None:
        self._margin_db = float(value)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _noise_floor_trend(self, spec_db: np.ndarray) -> np.ndarray:
        """Estimate per-bin noise floor via 25th-percentile chunk fit.

        Splits the inner spectrum (excluding edge roll-off) into n_chunks
        coarse segments, takes the 25th percentile of each, and interpolates
        a smooth curve across all bins. Edge bins are clamped to the nearest
        inner chunk value rather than extrapolated.
        """
        n = len(spec_db)
        if n < 2 * self._n_chunks:
            return np.full(n, float(np.percentile(spec_db, 25)), dtype=np.float32)

        edge = int(n * self._edge_fraction)
        inner_lo = edge
        inner_hi = n - edge
        inner_n = inner_hi - inner_lo
        chunk_size = max(1, inner_n // self._n_chunks)

        xs = np.empty(self._n_chunks, dtype=np.float32)
        ys = np.empty(self._n_chunks, dtype=np.float32)
        for i in range(self._n_chunks):
            a = inner_lo + i * chunk_size
            b = min(inner_hi, inner_lo + (i + 1) * chunk_size)
            chunk = spec_db[a:b]
            xs[i] = a + (b - a) / 2.0
            ys[i] = float(np.percentile(chunk, 25))

        return np.interp(
            np.arange(n, dtype=np.float32),
            xs,
            ys,
            left=float(ys[0]),
            right=float(ys[-1]),
        ).astype(np.float32)
