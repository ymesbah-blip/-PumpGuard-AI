"""Transparent baseline signal features."""
from __future__ import annotations
import numpy as np
from scipy.stats import kurtosis


def extract_features(signal: np.ndarray) -> dict[str, float]:
    x = np.asarray(signal, dtype=float)
    if x.ndim != 1 or x.size == 0:
        raise ValueError("signal must be a non-empty 1-D array")
    rms = float(np.sqrt(np.mean(x**2)))
    peak = float(np.max(np.abs(x)))
    return {
        "rms": rms,
        "peak": peak,
        "crest_factor": float(peak / rms) if rms else 0.0,
        "kurtosis": float(kurtosis(x, fisher=False, bias=False)) if x.size > 3 else float("nan"),
    }


def demo_health_score(features: dict[str, float]) -> float:
    """Toy score from 0-100; illustrative only, not calibrated to machinery."""
    score = 100.0 - min(100.0, max(0.0, (features["rms"] - 0.1) * 80))
    return round(float(score), 1)
