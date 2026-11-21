"""Transparent time-domain features and the combined feature pipeline."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.stats import kurtosis, skew

from ._validation import as_signal
from .bearings import BearingGeometry
from .health import demo_health_score  # re-exported for backward compatibility (v0.1)
from .spectral import spectral_features

__all__ = ["TIME_FEATURES", "demo_health_score", "extract_all_features", "extract_features"]

#: Keys returned by :func:`extract_features`, in order.
TIME_FEATURES: tuple[str, ...] = (
    "rms",
    "peak",
    "crest_factor",
    "kurtosis",
    "skewness",
    "std",
    "peak_to_peak",
    "shape_factor",
    "impulse_factor",
    "clearance_factor",
)


def extract_features(signal: ArrayLike) -> dict[str, float]:
    """Time-domain features of a 1-D signal.

    ``kurtosis`` uses the Pearson definition (Gaussian noise = 3, pure sine = 1.5).
    Ratios that are undefined (e.g. crest factor of an all-zero signal) are ``nan``.
    """
    x = as_signal(signal)
    nan = math.nan
    rms = float(np.sqrt(np.mean(x**2)))
    peak = float(np.max(np.abs(x)))
    abs_mean = float(np.mean(np.abs(x)))
    sqrt_mean_sq = float(np.mean(np.sqrt(np.abs(x)))) ** 2
    varying = x.size > 3 and float(np.ptp(x)) > 0
    return {
        "rms": rms,
        "peak": peak,
        "crest_factor": peak / rms if rms > 0 else nan,
        "kurtosis": float(kurtosis(x, fisher=False, bias=False)) if varying else nan,
        "skewness": float(skew(x, bias=False)) if varying else nan,
        "std": float(np.std(x)),
        "peak_to_peak": float(np.ptp(x)),
        "shape_factor": rms / abs_mean if abs_mean > 0 else nan,
        "impulse_factor": peak / abs_mean if abs_mean > 0 else nan,
        "clearance_factor": peak / sqrt_mean_sq if sqrt_mean_sq > 0 else nan,
    }


def extract_all_features(
    signal: ArrayLike,
    fs: float,
    *,
    rpm: float | None = None,
    n_vanes: int | None = None,
    bearing: BearingGeometry | None = None,
    envelope_band: tuple[float, float] | None = None,
) -> dict[str, float]:
    """Time-domain + frequency-domain features in one flat dictionary."""
    x = as_signal(signal)
    return {
        **extract_features(x),
        **spectral_features(
            x, fs, rpm=rpm, n_vanes=n_vanes, bearing=bearing, envelope_band=envelope_band
        ),
    }
