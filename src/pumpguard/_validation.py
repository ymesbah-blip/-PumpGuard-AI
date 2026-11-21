"""Small input-validation helpers shared across modules."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def as_signal(signal: ArrayLike, name: str = "signal") -> FloatArray:
    """Return ``signal`` as a finite, non-empty 1-D float64 array or raise ``ValueError``."""
    x = np.asarray(signal, dtype=np.float64)
    if x.ndim != 1 or x.size == 0:
        raise ValueError(f"{name} must be a non-empty 1-D array")
    if not np.all(np.isfinite(x)):
        raise ValueError(f"{name} contains NaN or infinite values")
    return x


def require_positive(name: str, value: float) -> float:
    """Return ``value`` as float if it is finite and > 0, else raise ``ValueError``."""
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    return v


def require_band(band: tuple[float, float], fs: float) -> tuple[float, float]:
    """Validate a ``(low, high)`` frequency band strictly inside ``(0, fs/2)``."""
    low, high = float(band[0]), float(band[1])
    if not (0 < low < high < fs / 2):
        raise ValueError(
            f"band must satisfy 0 < low < high < fs/2 ({fs / 2:g} Hz), got ({low:g}, {high:g})"
        )
    return low, high
