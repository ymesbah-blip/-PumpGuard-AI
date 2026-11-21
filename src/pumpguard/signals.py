"""Synthetic centrifugal-pump vibration signals for teaching and testing.

Everything produced here is **synthetic**: simplified, physically motivated
patterns that make signal-processing concepts visible. The signals are not
measurements, are not calibrated to any machine, and must never be presented
as real sensor data. Amplitudes are in arbitrary units.

Model (see ``docs/synthetic-model.md`` for details)::

    x(t) = A_1x sin(2 pi fr t + p1)              residual unbalance, always present
         + A_vp sin(2 pi Nv fr t + p2)           vane-pass tone, always present
         + sigma * n(t)                          white measurement noise
         + severity * fault_term(t)              condition-specific pattern

Random draws for the baseline happen first, so ``severity=0`` reproduces the
healthy signal exactly for the same seed.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy import signal as sps
from scipy.interpolate import CubicSpline

from ._validation import FloatArray, require_positive
from ._version import __version__
from .bearings import BearingGeometry

__all__ = [
    "CONDITIONS",
    "SignalConfig",
    "SyntheticSignal",
    "generate_signal",
    "simulate",
]

#: Supported synthetic operating conditions.
CONDITIONS: tuple[str, ...] = (
    "healthy",
    "imbalance",
    "misalignment",
    "bearing_outer",
    "bearing_inner",
    "cavitation_like",
)

#: Deprecated names kept for backward compatibility -> canonical name.
CONDITION_ALIASES: dict[str, str] = {"bearing_like": "bearing_outer"}

MIN_SAMPLES = 128

# Baseline amplitudes (arbitrary units).
_RESIDUAL_1X = 0.10
_VANE_PASS = 0.06

# Fault amplitudes at severity = 1 (arbitrary units).
_IMBALANCE_1X = 0.60
_MISALIGN = {1: 0.10, 2: 0.35, 3: 0.10}
_OUTER_IMPACT = 0.50
_INNER_IMPACT = 0.40
_INNER_MOD_DEPTH = 0.6
_CAVITATION = 0.12
_CAVITATION_KNOT_S = 0.05


def _default_bearing() -> BearingGeometry:
    return BearingGeometry.from_preset("6205")


@dataclass(frozen=True)
class SignalConfig:
    """All parameters of one synthetic recording.

    Attributes:
        condition: one of :data:`CONDITIONS`.
        fs: sampling rate in Hz.
        duration: length in seconds.
        rpm: shaft speed in revolutions per minute.
        seed: seed for :func:`numpy.random.default_rng` (``None`` = non-reproducible).
        noise_std: standard deviation of additive white noise.
        severity: fault amplitude multiplier (0 = no fault pattern).
        n_vanes: impeller vane count; sets the vane-pass frequency ``n_vanes * rpm / 60``.
        bearing: bearing geometry used for bearing-defect frequencies.
        resonance_hz: structural resonance excited by bearing impacts. ``None`` picks
            ``min(3000, 0.3 * fs)``.
        damping_ratio: damping ratio of that resonance.
        slip: random jitter of impact spacing (fraction), mimicking rolling-element slip.
    """

    condition: str = "healthy"
    fs: float = 12_000.0
    duration: float = 2.0
    rpm: float = 1800.0
    seed: int | None = 42
    noise_std: float = 0.05
    severity: float = 1.0
    n_vanes: int = 5
    bearing: BearingGeometry = field(default_factory=_default_bearing)
    resonance_hz: float | None = None
    damping_ratio: float = 0.05
    slip: float = 0.01

    def __post_init__(self) -> None:
        if self.condition in CONDITION_ALIASES:
            canonical = CONDITION_ALIASES[self.condition]
            warnings.warn(
                f"condition {self.condition!r} is deprecated; use {canonical!r}",
                DeprecationWarning,
                stacklevel=3,
            )
            object.__setattr__(self, "condition", canonical)
        if self.condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {sorted(CONDITIONS)}")

        fs = require_positive("fs", self.fs)
        duration = require_positive("duration", self.duration)
        rpm = require_positive("rpm", self.rpm)
        if round(fs * duration) < MIN_SAMPLES:
            raise ValueError(f"fs * duration must give at least {MIN_SAMPLES} samples")
        if not (math.isfinite(self.noise_std) and self.noise_std >= 0):
            raise ValueError("noise_std must be >= 0")
        if not (math.isfinite(self.severity) and self.severity >= 0):
            raise ValueError("severity must be >= 0")
        if int(self.n_vanes) != self.n_vanes or self.n_vanes < 1:
            raise ValueError("n_vanes must be a positive integer")
        if not 0 < self.damping_ratio < 1:
            raise ValueError("damping_ratio must be in (0, 1)")
        if not 0 <= self.slip < 0.2:
            raise ValueError("slip must be in [0, 0.2)")

        nyquist = fs / 2
        highest = max(3.0, float(self.n_vanes)) * rpm / 60.0
        if highest >= nyquist:
            raise ValueError(
                f"fs={fs:g} Hz is too low for rpm={rpm:g}: a {highest:.1f} Hz component "
                f"would alias (Nyquist = {nyquist:g} Hz)"
            )
        if self.resonance_hz is not None:
            require_positive("resonance_hz", self.resonance_hz)
            if self.resonance_hz >= 0.45 * fs:
                raise ValueError(
                    f"resonance_hz={self.resonance_hz:g} must be below 0.45 * fs "
                    f"({0.45 * fs:g} Hz) to avoid aliasing"
                )

    @property
    def n_samples(self) -> int:
        return round(self.fs * self.duration)

    @property
    def shaft_hz(self) -> float:
        return self.rpm / 60.0

    @property
    def resolved_resonance_hz(self) -> float:
        """Resonance actually used for impact responses."""
        if self.resonance_hz is not None:
            return float(self.resonance_hz)
        return min(3000.0, 0.3 * self.fs)

    def characteristic_frequencies(self) -> dict[str, float]:
        """Frequencies (Hz) at which this configuration places energy."""
        bearing = self.bearing.defect_frequencies(self.rpm)
        return {
            "shaft_1x": self.shaft_hz,
            "shaft_2x": 2 * self.shaft_hz,
            "shaft_3x": 3 * self.shaft_hz,
            "vane_pass": self.n_vanes * self.shaft_hz,
            "ftf": bearing.ftf,
            "bpfo": bearing.bpfo,
            "bpfi": bearing.bpfi,
            "bsf": bearing.bsf,
            "resonance": self.resolved_resonance_hz,
        }


@dataclass(frozen=True)
class SyntheticSignal:
    """A generated signal together with the configuration that produced it."""

    t: FloatArray
    x: FloatArray
    config: SignalConfig

    @property
    def fs(self) -> float:
        return float(self.config.fs)

    def metadata(self) -> dict[str, Any]:
        """JSON-serialisable provenance record. Always marks the data as synthetic."""
        return {
            "synthetic": True,
            "disclaimer": (
                "Synthetic signal from a simplified generator; not a measurement and "
                "not calibrated to any machine."
            ),
            "generator": "pumpguard.signals.simulate",
            "generator_version": __version__,
            "condition": self.config.condition,
            "fs": float(self.config.fs),
            "n_samples": int(self.x.size),
            "units": "arbitrary",
            "characteristic_frequencies_hz": self.config.characteristic_frequencies(),
            "config": asdict(self.config),
        }


# ------------------------------------------------------------------ generator


def simulate(config: SignalConfig) -> SyntheticSignal:
    """Generate one synthetic recording described by ``config``."""
    rng = np.random.default_rng(config.seed)
    n = config.n_samples
    fs = float(config.fs)
    t = np.arange(n, dtype=np.float64) / fs
    fr = config.shaft_hz

    # Baseline: drawn first so severity=0 reproduces "healthy" exactly.
    p1, p2 = rng.uniform(0.0, 2.0 * np.pi, size=2)
    x = (
        _RESIDUAL_1X * np.sin(2 * np.pi * fr * t + p1)
        + _VANE_PASS * np.sin(2 * np.pi * config.n_vanes * fr * t + p2)
        + config.noise_std * rng.standard_normal(n)
    )

    if config.severity > 0 and config.condition != "healthy":
        x = x + config.severity * _FAULTS[config.condition](t, config, rng)
    return SyntheticSignal(t=t, x=x, config=config)


def generate_signal(
    condition: str = "healthy",
    fs: float = 12_000.0,
    duration: float = 2.0,
    rpm: float = 1800.0,
    seed: int | None = 42,
    **kwargs: Any,
) -> tuple[FloatArray, FloatArray]:
    """Return ``(t, x)`` for a synthetic signal. Extra keyword arguments go to
    :class:`SignalConfig` (e.g. ``severity``, ``noise_std``, ``n_vanes``).

    Kept for backward compatibility with v0.1; prefer :func:`simulate` for new code
    because it also returns provenance metadata.
    """
    cfg = SignalConfig(condition=condition, fs=fs, duration=duration, rpm=rpm, seed=seed, **kwargs)
    sig = simulate(cfg)
    return sig.t, sig.x


# --------------------------------------------------------------- fault terms

_Fault = Callable[[FloatArray, SignalConfig, np.random.Generator], FloatArray]


def _imbalance(t: FloatArray, cfg: SignalConfig, rng: np.random.Generator) -> FloatArray:
    phase = rng.uniform(0.0, 2.0 * np.pi)
    return _IMBALANCE_1X * np.sin(2 * np.pi * cfg.shaft_hz * t + phase)


def _misalignment(t: FloatArray, cfg: SignalConfig, rng: np.random.Generator) -> FloatArray:
    out = np.zeros_like(t)
    for order, amp in _MISALIGN.items():
        out += amp * np.sin(2 * np.pi * order * cfg.shaft_hz * t + rng.uniform(0.0, 2.0 * np.pi))
    return out


def _bearing_outer(t: FloatArray, cfg: SignalConfig, rng: np.random.Generator) -> FloatArray:
    bpfo = cfg.bearing.defect_frequencies(cfg.rpm).bpfo
    return _OUTER_IMPACT * _impact_train(t, cfg, rng, bpfo)


def _bearing_inner(t: FloatArray, cfg: SignalConfig, rng: np.random.Generator) -> FloatArray:
    bpfi = cfg.bearing.defect_frequencies(cfg.rpm).bpfi
    return _INNER_IMPACT * _impact_train(
        t, cfg, rng, bpfi, mod_hz=cfg.shaft_hz, mod_depth=_INNER_MOD_DEPTH
    )


def _cavitation(t: FloatArray, cfg: SignalConfig, rng: np.random.Generator) -> FloatArray:
    """Broadband high-frequency noise with slowly varying, bursty amplitude."""
    fs = float(cfg.fs)
    low, high = min(2000.0, 0.15 * fs), min(5000.0, 0.40 * fs)
    sos = sps.butter(4, [low, high], btype="bandpass", fs=fs, output="sos")
    carrier = sps.sosfiltfilt(sos, rng.standard_normal(t.size))
    carrier /= max(float(np.std(carrier)), 1e-12)
    # Slow random burst envelope: cubic spline through random knots every 50 ms.
    # (A very low-cutoff IIR filter here would create large edge transients.)
    knot_t = np.arange(math.ceil(t.size / fs / _CAVITATION_KNOT_S) + 2) * _CAVITATION_KNOT_S
    z = CubicSpline(knot_t, rng.standard_normal(knot_t.size))(t)
    z /= max(float(np.std(z)), 1e-12)
    envelope = 0.5 + np.abs(z)
    envelope /= float(np.mean(envelope))
    result: FloatArray = _CAVITATION * envelope * carrier
    return result


def _impact_train(
    t: FloatArray,
    cfg: SignalConfig,
    rng: np.random.Generator,
    rate_hz: float,
    mod_hz: float | None = None,
    mod_depth: float = 0.0,
) -> FloatArray:
    """Repetitive impacts at ``rate_hz`` exciting a damped resonance.

    Impacts are placed at their exact (sub-sample) times so the repetition rate is
    not quantised to the sampling grid. Spacing is jittered by ``cfg.slip``.
    With ``mod_hz`` set, impact amplitude varies between ``1 - mod_depth`` and 1
    at that rate (inner-race defect passing through the load zone).
    """
    fs = float(cfg.fs)
    n = t.size
    duration = n / fs
    period = 1.0 / rate_hz

    n_imp = math.ceil(duration * rate_hz) + 2
    spacing = period * (1.0 + cfg.slip * rng.standard_normal(n_imp))
    spacing = np.clip(spacing, 0.5 * period, 1.5 * period)
    times = rng.uniform(0.0, period) + np.concatenate(([0.0], np.cumsum(spacing[:-1])))
    times = times[times < duration]

    amps = np.ones_like(times)
    if mod_hz is not None and mod_depth > 0:
        phase = rng.uniform(0.0, 2.0 * np.pi)
        amps = 1.0 - mod_depth / 2.0 * (1.0 - np.cos(2 * np.pi * mod_hz * times + phase))

    f_n = cfg.resolved_resonance_hz
    zeta = cfg.damping_ratio
    decay = zeta * 2 * np.pi * f_n
    omega_d = 2 * np.pi * f_n * math.sqrt(1.0 - zeta**2)
    window = math.ceil(math.log(1e3) / decay * fs) + 1  # until amplitude < 1e-3

    out = np.zeros(n)
    for tk, ak in zip(times, amps, strict=True):
        i0 = math.ceil(tk * fs)
        if i0 >= n:
            continue
        i1 = min(n, i0 + window)
        tau = t[i0:i1] - tk
        out[i0:i1] += ak * np.exp(-decay * tau) * np.sin(omega_d * tau)
    return out


_FAULTS: dict[str, _Fault] = {
    "imbalance": _imbalance,
    "misalignment": _misalignment,
    "bearing_outer": _bearing_outer,
    "bearing_inner": _bearing_inner,
    "cavitation_like": _cavitation,
}
