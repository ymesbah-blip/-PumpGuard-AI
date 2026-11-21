"""Synthetic vibration signals for demos only; not real machine measurements."""
from __future__ import annotations
import numpy as np


def generate_signal(condition: str = "healthy", fs: int = 2000, duration: float = 2.0,
                  rpm: float = 1800, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate an illustrative vibration signal and time vector.

    Supported conditions: healthy, imbalance, bearing_like.
    Patterns are intentionally simplified for teaching signal-processing concepts.
    """
    allowed = {"healthy", "imbalance", "bearing_like"}
    if condition not in allowed:
        raise ValueError(f"condition must be one of {sorted(allowed)}")
    if fs <= 0 or duration <= 0 or rpm <= 0:
        raise ValueError("fs, duration, and rpm must be positive")
    rng = np.random.default_rng(seed)
    n = int(fs * duration)
    t = np.arange(n) / fs
    f_rot = rpm / 60.0
    noise = 0.08 * rng.standard_normal(n)
    signal = noise + 0.12 * np.sin(2 * np.pi * f_rot * t)
    if condition == "imbalance":
        signal += 0.65 * np.sin(2 * np.pi * f_rot * t)
    elif condition == "bearing_like":
        impacts = np.zeros(n)
        interval = max(1, int(fs / (f_rot * 4.2)))
        impacts[::interval] = 1.0
        # Simple decaying impulse response to illustrate repetitive impacts.
        impulse_t = np.arange(max(1, int(0.025 * fs))) / fs
        response = np.exp(-impulse_t * 180) * np.sin(2 * np.pi * 700 * impulse_t)
        signal += np.convolve(impacts, response, mode="full")[:n] * 0.12
    return t, signal
