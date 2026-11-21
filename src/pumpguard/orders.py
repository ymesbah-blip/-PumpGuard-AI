"""Mechanism frequencies: where a rotating pump puts energy, from speed and geometry.

These functions describe the machine. Whether a sensor can observe a frequency
is a separate question, answered by :mod:`pumpguard.sensors`. Energy at one of
these frequencies is **not** by itself evidence of a fault: every healthy pump
has a 1x and a vane-pass component.
"""

from __future__ import annotations

import math

__all__ = ["characteristic_frequencies", "rpm_from_supply_frequency", "shaft_hz", "vane_pass_hz"]


def _positive(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    return v


def shaft_hz(rpm: float) -> float:
    """Shaft rotation frequency f1 = rpm / 60 in Hz."""
    return _positive("rpm", rpm) / 60.0


def rpm_from_supply_frequency(supply_hz: float, poles: int = 2, slip: float = 0.0) -> float:
    """Induction-motor speed from the drive (VSD) output frequency.

    rpm = 120 * f / poles * (1 - slip). A 2-pole ESP motor at 60 Hz turns at
    3600 rpm synchronous; real slip is typically a few percent and depends on load,
    so pass the measured or nameplate slip rather than assuming zero.
    """
    f = _positive("supply_hz", supply_hz)
    if int(poles) != poles or poles < 2 or poles % 2:
        raise ValueError("poles must be an even integer >= 2")
    if not 0.0 <= slip < 0.2:
        raise ValueError("slip must be in [0, 0.2)")
    return 120.0 * f / poles * (1.0 - slip)


def vane_pass_hz(rpm: float, n_vanes: int, harmonic: int = 1) -> float:
    """Vane-pass frequency harmonic * n_vanes * f1 (impeller vanes passing a fixed point)."""
    if int(n_vanes) != n_vanes or n_vanes < 1:
        raise ValueError(
            "n_vanes must be a positive integer (impeller vane count from the drawing)"
        )
    if int(harmonic) != harmonic or harmonic < 1:
        raise ValueError("harmonic must be a positive integer")
    return harmonic * n_vanes * shaft_hz(rpm)


def characteristic_frequencies(
    rpm: float, n_vanes: int | None = None, harmonics: int = 3
) -> dict[str, float]:
    """Shaft orders 1x..Nx and, if the vane count is known, vane-pass harmonics."""
    if int(harmonics) != harmonics or harmonics < 1:
        raise ValueError("harmonics must be a positive integer")
    f1 = shaft_hz(rpm)
    out = {f"{k}x": k * f1 for k in range(1, harmonics + 1)}
    if n_vanes is not None:
        out.update(
            {f"vane_pass_{k}": vane_pass_hz(rpm, n_vanes, k) for k in range(1, harmonics + 1)}
        )
    return out
