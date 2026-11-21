"""Frequency-domain and envelope-analysis features.

Conventions:

* :func:`amplitude_spectrum` is single-sided and corrected for the window's
  coherent gain, so a sine of amplitude ``A`` centred on a bin reads ``A``.
* The signal mean is removed before any spectrum is computed.
* Envelope analysis = band-pass around a structural resonance -> Hilbert
  magnitude -> amplitude spectrum. Repetitive impacts (bearing defects) show up
  as peaks at their repetition rate.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike
from scipy import signal as sps

from ._validation import FloatArray, as_signal, require_band, require_positive
from .bearings import BearingGeometry

__all__ = [
    "amplitude_spectrum",
    "band_energy_ratio",
    "default_envelope_band",
    "envelope",
    "envelope_spectrum",
    "order_amplitudes",
    "peak_near",
    "peak_to_median_ratio",
    "spectral_centroid",
    "spectral_features",
]


def amplitude_spectrum(
    signal: ArrayLike, fs: float, window: str | None = "hann"
) -> tuple[FloatArray, FloatArray]:
    """Single-sided amplitude spectrum ``(freqs_hz, amplitude)``."""
    x = as_signal(signal)
    fs = require_positive("fs", fs)
    x = x - x.mean()
    n = x.size
    w = sps.get_window(window, n) if window else np.ones(n)
    spectrum = np.fft.rfft(x * w)
    amp = np.abs(spectrum) * 2.0 / float(np.sum(w))
    amp[0] /= 2.0
    if n % 2 == 0:
        amp[-1] /= 2.0
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    return freqs, amp


def peak_near(freqs: FloatArray, amp: FloatArray, f0: float, tol: float | None = None) -> float:
    """Largest amplitude within ``f0 +/- tol`` Hz (default ``max(3 bins, 2 % of f0)``).

    Returns ``nan`` when ``f0`` lies outside the spectrum.
    """
    if freqs.size < 2 or not 0 < f0 <= freqs[-1]:
        return math.nan
    df = float(freqs[1] - freqs[0])
    tol = max(3.0 * df, 0.02 * f0) if tol is None else tol
    mask = np.abs(freqs - f0) <= tol
    return float(amp[mask].max()) if mask.any() else math.nan


def peak_to_median_ratio(freqs: FloatArray, amp: FloatArray, f0: float) -> float:
    """Peak near ``f0`` divided by the median spectrum level over ``(0, 5 * f0]``.

    A dimensionless prominence that is less sensitive to overall gain than the raw
    peak amplitude.
    """
    peak = peak_near(freqs, amp, f0)
    ref_mask = (freqs > 0) & (freqs <= 5.0 * f0)
    if math.isnan(peak) or not ref_mask.any():
        return math.nan
    ref = float(np.median(amp[ref_mask]))
    return peak / ref if ref > 0 else math.nan


def order_amplitudes(
    signal: ArrayLike, fs: float, rpm: float, orders: tuple[float, ...] = (1, 2, 3)
) -> dict[str, float]:
    """Spectrum amplitude at multiples of shaft speed, keyed ``amp_1x``, ``amp_2x``..."""
    fr = require_positive("rpm", rpm) / 60.0
    freqs, amp = amplitude_spectrum(signal, fs)
    return {f"amp_{order:g}x": peak_near(freqs, amp, order * fr) for order in orders}


def _power(signal: ArrayLike, fs: float) -> tuple[FloatArray, FloatArray]:
    x = as_signal(signal)
    fs = require_positive("fs", fs)
    freqs, power = sps.periodogram(x, fs=fs, window="hann", detrend="constant")
    return np.asarray(freqs, dtype=np.float64), np.asarray(power, dtype=np.float64)


def band_energy_ratio(signal: ArrayLike, fs: float, low: float, high: float) -> float:
    """Fraction of (non-DC) signal power between ``low`` and ``high`` Hz."""
    freqs, power = _power(signal, fs)
    total = float(power[1:].sum())
    if total <= 0:
        return math.nan
    band = (freqs >= low) & (freqs <= high)
    return float(power[band].sum()) / total


def spectral_centroid(signal: ArrayLike, fs: float) -> float:
    """Power-weighted mean frequency in Hz."""
    freqs, power = _power(signal, fs)
    total = float(power.sum())
    return float(np.sum(freqs * power) / total) if total > 0 else math.nan


def default_envelope_band(fs: float) -> tuple[float, float]:
    """Default demodulation band ``(0.1 fs, 0.4 fs)``.

    For real data, choose a band around the structural resonance instead
    (e.g. with a kurtogram — see the roadmap).
    """
    fs = require_positive("fs", fs)
    return 0.1 * fs, 0.4 * fs


def envelope(signal: ArrayLike, fs: float, band: tuple[float, float] | None = None) -> FloatArray:
    """Band-pass filter then take the Hilbert magnitude."""
    x = as_signal(signal)
    fs = require_positive("fs", fs)
    low, high = require_band(band or default_envelope_band(fs), fs)
    sos = sps.butter(4, [low, high], btype="bandpass", fs=fs, output="sos")
    filtered = sps.sosfiltfilt(sos, x)
    return np.asarray(np.abs(sps.hilbert(filtered)), dtype=np.float64)


def envelope_spectrum(
    signal: ArrayLike, fs: float, band: tuple[float, float] | None = None
) -> tuple[FloatArray, FloatArray]:
    """Amplitude spectrum of the envelope ``(freqs_hz, amplitude)``."""
    return amplitude_spectrum(envelope(signal, fs, band), fs)


def spectral_features(
    signal: ArrayLike,
    fs: float,
    *,
    rpm: float | None = None,
    n_vanes: int | None = None,
    bearing: BearingGeometry | None = None,
    envelope_band: tuple[float, float] | None = None,
    hf_cutoff_hz: float = 1000.0,
) -> dict[str, float]:
    """Frequency-domain features. Speed-dependent ones need ``rpm``.

    Always: ``spectral_centroid_hz``, ``hf_energy_ratio`` (power above ``hf_cutoff_hz``).
    With ``rpm``: ``amp_1x``, ``amp_2x``, ``amp_3x``.
    With ``rpm`` and ``n_vanes``: ``amp_vane_pass``.
    With ``rpm`` and ``bearing``: ``env_bpfo_ratio``, ``env_bpfi_ratio`` (envelope
    spectrum peak-to-median ratio at the defect frequencies).
    """
    x = as_signal(signal)
    fs = require_positive("fs", fs)
    feats: dict[str, float] = {
        "spectral_centroid_hz": spectral_centroid(x, fs),
        "hf_energy_ratio": (
            band_energy_ratio(x, fs, hf_cutoff_hz, fs / 2) if hf_cutoff_hz < fs / 2 else math.nan
        ),
    }
    if rpm is None:
        return feats

    feats.update(order_amplitudes(x, fs, rpm))
    fr = rpm / 60.0
    if n_vanes is not None:
        freqs, amp = amplitude_spectrum(x, fs)
        feats["amp_vane_pass"] = peak_near(freqs, amp, n_vanes * fr)
    if bearing is not None:
        defects = bearing.defect_frequencies(rpm)
        env_f, env_a = envelope_spectrum(x, fs, envelope_band)
        feats["env_bpfo_ratio"] = peak_to_median_ratio(env_f, env_a, defects.bpfo)
        feats["env_bpfi_ratio"] = peak_to_median_ratio(env_f, env_a, defects.bpfi)
    return feats
