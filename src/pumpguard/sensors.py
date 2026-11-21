"""Sensor functions: what an instrument can observe of the mechanism.

Kept separate from :mod:`pumpguard.orders` and :mod:`pumpguard.hydraulics` on
purpose. A pump can have strong vane-pass excitation that a sensor cannot see
because it samples too slowly or filters it out. Typical SCADA vibration
channels report one overall level per minute: they cannot resolve shaft orders,
vane pass or bearing defect frequencies, whatever the machine does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from scipy import signal as sps

from ._validation import FloatArray, as_signal
from .units import STANDARD_GRAVITY

__all__ = [
    "ANALYZER_FACTOR",
    "SensorSpec",
    "acceleration_from_voltage",
    "measure",
    "minimum_sample_rate_hz",
    "resolvable",
    "sampling_report",
]

#: Common analyser practice: sample at >= 2.56 x the highest frequency of interest,
#: leaving room for a realistic anti-alias filter roll-off below Nyquist.
ANALYZER_FACTOR = 2.56


@dataclass(frozen=True)
class SensorSpec:
    """What a channel measures and how it is sampled.

    ``anti_alias_cutoff_hz`` is the -3 dB corner of the analogue/digital
    low-pass applied before sampling; it must lie below Nyquist.
    """

    quantity: str
    unit: str
    sample_rate_hz: float
    anti_alias_cutoff_hz: float | None = None
    sensitivity: float | None = None
    sensitivity_unit: str | None = None
    full_scale: float | None = None
    resolution: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.quantity.strip() or not self.unit.strip():
            raise ValueError("quantity and unit are required")
        fs = float(self.sample_rate_hz)
        if not math.isfinite(fs) or fs <= 0:
            raise ValueError("sample_rate_hz must be a positive finite number")
        if self.anti_alias_cutoff_hz is not None and not 0 < self.anti_alias_cutoff_hz < fs / 2:
            raise ValueError(
                f"anti_alias_cutoff_hz must be in (0, fs/2 = {fs / 2:g} Hz): otherwise content "
                "above Nyquist aliases into the band"
            )
        for name in ("sensitivity", "full_scale", "resolution"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be a positive finite number")

    @classmethod
    def from_interval(cls, sample_interval_s: float, **kwargs: Any) -> SensorSpec:
        """Build a spec from a logging interval, e.g. 60 s for one-minute SCADA."""
        if not math.isfinite(sample_interval_s) or sample_interval_s <= 0:
            raise ValueError("sample_interval_s must be positive")
        return cls(sample_rate_hz=1.0 / sample_interval_s, **kwargs)

    @property
    def nyquist_hz(self) -> float:
        return self.sample_rate_hz / 2.0


def minimum_sample_rate_hz(f_max_hz: float, factor: float = ANALYZER_FACTOR) -> float:
    """Sampling rate needed to observe content up to ``f_max_hz``."""
    if not math.isfinite(f_max_hz) or f_max_hz <= 0 or factor < 2:
        raise ValueError("f_max_hz must be positive and factor >= 2")
    return factor * f_max_hz


def resolvable(spec: SensorSpec, frequency_hz: float) -> tuple[bool, str]:
    """Can ``spec`` observe a component at ``frequency_hz``? Returns (ok, reason)."""
    f = float(frequency_hz)
    if not math.isfinite(f) or f <= 0:
        raise ValueError("frequency_hz must be positive")
    if f >= spec.nyquist_hz:
        return False, f"above Nyquist ({spec.nyquist_hz:.4g} Hz): cannot be observed"
    if spec.anti_alias_cutoff_hz is not None and f > spec.anti_alias_cutoff_hz:
        return False, f"above the anti-alias cutoff ({spec.anti_alias_cutoff_hz:.4g} Hz)"
    if spec.sample_rate_hz < ANALYZER_FACTOR * f:
        return False, f"below {ANALYZER_FACTOR}x sampling margin (marginal, avoid)"
    return True, "observable"


def sampling_report(spec: SensorSpec, frequencies_hz: dict[str, float]) -> list[dict[str, Any]]:
    """One row per named frequency: can this sensor observe it, and why (not)."""
    rows = []
    for name, f in frequencies_hz.items():
        ok, reason = resolvable(spec, f)
        rows.append({"name": name, "frequency_hz": float(f), "observable": ok, "reason": reason})
    return rows


def acceleration_from_voltage(volts: ArrayLike, sensitivity_mv_per_g: float) -> FloatArray:
    """Convert accelerometer output (V) to m/s^2 using its calibrated sensitivity (mV/g)."""
    if not math.isfinite(sensitivity_mv_per_g) or sensitivity_mv_per_g <= 0:
        raise ValueError("sensitivity_mv_per_g must be positive (from the calibration sheet)")
    v = as_signal(volts, "volts")
    result: FloatArray = v * 1000.0 / sensitivity_mv_per_g * STANDARD_GRAVITY
    return result


def measure(
    x: ArrayLike,
    fs_in_hz: float,
    spec: SensorSpec,
    *,
    noise_std: float = 0.0,
    rng: np.random.Generator | None = None,
) -> FloatArray:
    """Simulate observing a high-rate (mechanism) signal through ``spec``.

    Steps: anti-alias low-pass (8th-order Butterworth, zero phase) at the spec's
    cutoff (default 0.4 * output rate), integer decimation to the sensor rate,
    optional white noise, clipping to full scale, quantisation to the resolution.
    ``fs_in_hz`` must be an integer multiple of the sensor rate.
    """
    sig = as_signal(x)
    if not math.isfinite(fs_in_hz) or fs_in_hz <= 0:
        raise ValueError("fs_in_hz must be positive")
    factor = fs_in_hz / spec.sample_rate_hz
    step = round(factor)
    if step < 1 or abs(factor - step) > 1e-9 * factor:
        raise ValueError("fs_in_hz must be an integer multiple of the sensor sample rate")
    if noise_std < 0:
        raise ValueError("noise_std must be >= 0")
    out = sig
    if step > 1:
        cutoff = spec.anti_alias_cutoff_hz or 0.4 * spec.sample_rate_hz
        sos = sps.butter(8, cutoff, btype="lowpass", fs=fs_in_hz, output="sos")
        out = sps.sosfiltfilt(sos, out)[::step]
    if noise_std > 0:
        out = out + (rng or np.random.default_rng(0)).normal(0.0, noise_std, out.size)
    if spec.full_scale is not None:
        out = np.clip(out, -spec.full_scale, spec.full_scale)
    if spec.resolution is not None:
        out = np.round(out / spec.resolution) * spec.resolution
    return np.asarray(out, dtype=np.float64)
