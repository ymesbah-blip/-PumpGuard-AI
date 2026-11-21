"""Pump hydraulics in SI units: operating point, multistage pump curve, well system.

Mechanism functions only: what the pump and well do physically. How sensors see
it lives in :mod:`pumpguard.sensors`.

Assumptions (state them next to any result):

* Single-phase, Newtonian liquid. No viscosity or free-gas correction of the pump
  curve (both degrade ESP performance in practice).
* Affinity laws (Q ~ N, H ~ N^2, P ~ N^3) hold at constant efficiency. They are
  approximations, not exact laws: they degrade with viscosity, Reynolds-number
  effects and gas.
* The operating point at any speed is the **intersection** of the pump curve
  with the system curve. Scaling a measured flow by N2/N1 is only valid when the
  system curve is a parabola through the origin (pure friction, no static lift),
  which is never the case for a well.
* No extrapolation beyond the catalog flow range.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.polynomial import Polynomial
from scipy.optimize import brentq

from .units import STANDARD_GRAVITY

__all__ = [
    "OperatingPoint",
    "OperatingPointError",
    "OperatingPointResult",
    "PumpCurve",
    "WellSystem",
    "affinity_scale",
    "head_from_pressure",
    "hydraulic_power_w",
    "npsh_available_m",
    "pressure_from_head",
    "solve_operating_point",
]


def _finite(
    name: str, value: float, *, minimum: float | None = None, strict: bool = False
) -> float:
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if minimum is not None and (v <= minimum if strict else v < minimum):
        op = ">" if strict else ">="
        raise ValueError(f"{name} must be {op} {minimum:g}, got {v:g}")
    return v


# ------------------------------------------------------------------ basics


def head_from_pressure(
    delta_p_pa: float, density_kg_m3: float, g: float = STANDARD_GRAVITY
) -> float:
    """Head in metres of fluid: H = dp / (rho g)."""
    rho = _finite("density_kg_m3", density_kg_m3, minimum=0, strict=True)
    return _finite("delta_p_pa", delta_p_pa) / (rho * g)


def pressure_from_head(head_m: float, density_kg_m3: float, g: float = STANDARD_GRAVITY) -> float:
    """Pressure in Pa: dp = rho g H."""
    rho = _finite("density_kg_m3", density_kg_m3, minimum=0, strict=True)
    return rho * g * _finite("head_m", head_m)


def hydraulic_power_w(
    flow_m3_s: float, head_m: float, density_kg_m3: float, g: float = STANDARD_GRAVITY
) -> float:
    """Hydraulic (water) power P = rho g Q H in watts."""
    q = _finite("flow_m3_s", flow_m3_s, minimum=0)
    rho = _finite("density_kg_m3", density_kg_m3, minimum=0, strict=True)
    return rho * g * q * _finite("head_m", head_m)


def affinity_scale(
    flow_m3_s: float,
    head_m: float,
    power_w: float | None,
    speed_from_rpm: float,
    speed_to_rpm: float,
) -> tuple[float, float, float | None]:
    """Scale one point of a pump curve to another speed (Q ~ N, H ~ N^2, P ~ N^3).

    This moves a point **along the pump's own curve family**. It does not give the
    new operating point of a pump in a system; use :func:`solve_operating_point`.
    """
    n1 = _finite("speed_from_rpm", speed_from_rpm, minimum=0, strict=True)
    n2 = _finite("speed_to_rpm", speed_to_rpm, minimum=0, strict=True)
    r = n2 / n1
    power = None if power_w is None else _finite("power_w", power_w) * r**3
    return _finite("flow_m3_s", flow_m3_s) * r, _finite("head_m", head_m) * r**2, power


def npsh_available_m(
    intake_pressure_abs_pa: float,
    vapor_pressure_pa: float,
    density_kg_m3: float,
    velocity_m_s: float = 0.0,
    g: float = STANDARD_GRAVITY,
) -> float:
    """NPSHa = (p_abs - p_vapour) / (rho g) + v^2 / (2 g) at the pump intake.

    Single-phase concept. In wells with free gas (pressure below bubble point) the
    relevant limit is gas handling, which this formula does not describe.
    """
    p = _finite("intake_pressure_abs_pa", intake_pressure_abs_pa, minimum=0)
    pv = _finite("vapor_pressure_pa", vapor_pressure_pa, minimum=0)
    rho = _finite("density_kg_m3", density_kg_m3, minimum=0, strict=True)
    v = _finite("velocity_m_s", velocity_m_s)
    return (p - pv) / (rho * g) + v**2 / (2 * g)


# --------------------------------------------------------- operating point


@dataclass(frozen=True)
class OperatingPoint:
    """A validated pump operating point in SI units.

    Optional quantities are ``None`` when not measured; nothing is guessed.
    """

    flow_m3_s: float
    head_m: float
    speed_rpm: float
    density_kg_m3: float
    temperature_c: float | None = None
    shaft_power_w: float | None = None
    npsh_available_m: float | None = None
    npsh_required_m: float | None = None

    def __post_init__(self) -> None:
        _finite("flow_m3_s", self.flow_m3_s, minimum=0)
        _finite("head_m", self.head_m, minimum=0)
        _finite("speed_rpm", self.speed_rpm, minimum=0, strict=True)
        _finite("density_kg_m3", self.density_kg_m3, minimum=0, strict=True)
        if self.temperature_c is not None:
            _finite("temperature_c", self.temperature_c, minimum=-273.15)
        if self.shaft_power_w is not None:
            _finite("shaft_power_w", self.shaft_power_w, minimum=0, strict=True)
            if self.hydraulic_power_w > self.shaft_power_w:
                raise ValueError(
                    f"hydraulic power {self.hydraulic_power_w:.4g} W exceeds shaft power "
                    f"{self.shaft_power_w:.4g} W: inconsistent measurements or units"
                )
        for name in ("npsh_available_m", "npsh_required_m"):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)

    @property
    def shaft_hz(self) -> float:
        return self.speed_rpm / 60.0

    @property
    def hydraulic_power_w(self) -> float:
        return hydraulic_power_w(self.flow_m3_s, self.head_m, self.density_kg_m3)

    @property
    def efficiency(self) -> float | None:
        """Hydraulic power / shaft power, or ``None`` if shaft power is unknown."""
        if self.shaft_power_w is None:
            return None
        return self.hydraulic_power_w / self.shaft_power_w

    @property
    def npsh_margin_m(self) -> float | None:
        if self.npsh_available_m is None or self.npsh_required_m is None:
            return None
        return self.npsh_available_m - self.npsh_required_m


# -------------------------------------------------------------- pump curve


@dataclass(frozen=True)
class PumpCurve:
    """Head-flow curve of one stage at a reference speed, for an ``n_stages`` pump.

    Catalog points are fitted with a polynomial (scaled domain, well conditioned).
    The fitted head must decrease with flow over the catalog range, so the curve
    can be inverted uniquely. No extrapolation outside the catalog flow range.
    """

    flow_m3_s: tuple[float, ...]
    head_m_per_stage: tuple[float, ...]
    reference_speed_rpm: float
    n_stages: int = 1
    degree: int = 3
    bep_flow_m3_s: float | None = None
    operating_range_m3_s: tuple[float, float] | None = None
    name: str = "pump"
    source: str = "unspecified"
    _poly: Polynomial = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        q = np.asarray(self.flow_m3_s, dtype=np.float64)
        h = np.asarray(self.head_m_per_stage, dtype=np.float64)
        if q.ndim != 1 or q.shape != h.shape:
            raise ValueError("flow and head points must be 1-D and equally long")
        if q.size < self.degree + 2:
            raise ValueError(f"need at least degree + 2 = {self.degree + 2} catalog points")
        if not (np.all(np.isfinite(q)) and np.all(np.isfinite(h))):
            raise ValueError("catalog points must be finite")
        if q[0] < 0 or np.any(np.diff(q) <= 0):
            raise ValueError("catalog flows must be >= 0 and strictly increasing")
        if np.any(h <= 0):
            raise ValueError("catalog heads must be > 0 (truncate the curve before zero head)")
        if not 1 <= self.degree <= 6:
            raise ValueError("degree must be between 1 and 6")
        if int(self.n_stages) != self.n_stages or self.n_stages < 1:
            raise ValueError("n_stages must be a positive integer")
        _finite("reference_speed_rpm", self.reference_speed_rpm, minimum=0, strict=True)
        poly = Polynomial.fit(q, h, self.degree)
        grid = np.linspace(q[0], q[-1], 512)
        slope = poly.deriv()(grid)
        if np.any(slope > 1e-9 * float(np.max(h)) / max(float(q[-1]), 1e-12)):
            raise ValueError(
                "fitted head rises with flow somewhere in the catalog range; check the points "
                "or lower the polynomial degree (the curve must be invertible)"
            )
        if self.bep_flow_m3_s is not None and not q[0] <= self.bep_flow_m3_s <= q[-1]:
            raise ValueError("bep_flow_m3_s must lie inside the catalog flow range")
        if self.operating_range_m3_s is not None:
            lo, hi = self.operating_range_m3_s
            if not q[0] <= lo < hi <= q[-1]:
                raise ValueError("operating_range_m3_s must lie inside the catalog flow range")
        object.__setattr__(self, "_poly", poly)

    # -- fit quality
    @property
    def rmse_m(self) -> float:
        """RMS residual of the polynomial fit, metres per stage."""
        q = np.asarray(self.flow_m3_s)
        h = np.asarray(self.head_m_per_stage)
        return float(np.sqrt(np.mean((self._poly(q) - h) ** 2)))

    # -- speed scaling
    def _ratio(self, speed_rpm: float) -> float:
        return _finite("speed_rpm", speed_rpm, minimum=0, strict=True) / self.reference_speed_rpm

    def flow_range_m3_s(self, speed_rpm: float) -> tuple[float, float]:
        r = self._ratio(speed_rpm)
        return self.flow_m3_s[0] * r, self.flow_m3_s[-1] * r

    def stage_head_m(self, flow_m3_s: float, speed_rpm: float) -> float:
        """Head per stage at ``speed_rpm`` (affinity-scaled catalog curve)."""
        r = self._ratio(speed_rpm)
        q = _finite("flow_m3_s", flow_m3_s)
        lo, hi = self.flow_range_m3_s(speed_rpm)
        tol = 1e-12 * max(hi, 1.0)
        if not lo - tol <= q <= hi + tol:
            raise ValueError(
                f"flow {q:.6g} m^3/s outside catalog range [{lo:.6g}, {hi:.6g}] at "
                f"{speed_rpm:g} rpm (no extrapolation)"
            )
        return float(r**2 * self._poly(q / r))

    def head_m(self, flow_m3_s: float, speed_rpm: float) -> float:
        """Total head of all stages."""
        return self.n_stages * self.stage_head_m(flow_m3_s, speed_rpm)

    def flow_at_head(self, head_m: float, speed_rpm: float) -> float:
        """Invert the curve: flow giving total ``head_m`` at ``speed_rpm``."""
        target = _finite("head_m", head_m)
        lo, hi = self.flow_range_m3_s(speed_rpm)
        h_lo, h_hi = self.head_m(lo, speed_rpm), self.head_m(hi, speed_rpm)
        if not h_hi <= target <= h_lo:
            raise ValueError(
                f"head {target:.4g} m outside [{h_hi:.4g}, {h_lo:.4g}] m covered by the curve "
                f"at {speed_rpm:g} rpm"
            )
        if target == h_lo:
            return lo
        if target == h_hi:
            return hi
        return float(brentq(lambda x: self.head_m(x, speed_rpm) - target, lo, hi, xtol=1e-12))

    def bep_flow_at(self, speed_rpm: float) -> float:
        if self.bep_flow_m3_s is None:
            raise ValueError("bep_flow_m3_s not provided for this curve")
        return self.bep_flow_m3_s * self._ratio(speed_rpm)

    def operating_range_at(self, speed_rpm: float) -> tuple[float, float]:
        if self.operating_range_m3_s is None:
            raise ValueError("operating_range_m3_s not provided for this curve")
        r = self._ratio(speed_rpm)
        return self.operating_range_m3_s[0] * r, self.operating_range_m3_s[1] * r


# ------------------------------------------------------------ well system


@dataclass(frozen=True)
class WellSystem:
    """Pressure the pump must overcome in a producing well (single-phase liquid).

    * Inflow (linear IPR): p_wf = p_r - Q / PI at the reservoir datum.
    * Intake pressure: p_in = p_wf - ``intake_offset_pa`` (hydrostatic column
      between datum and pump intake; 0 if the pump sits at the datum).
    * Required discharge pressure: p_out = p_wh + rho g L + k Q^2, with L the
      vertical lift from intake to wellhead and k a tubing-friction coefficient.
    * Required head: (p_out - p_in) / (rho g).
    """

    reservoir_pressure_pa: float
    productivity_index_m3_s_per_pa: float
    wellhead_pressure_pa: float
    lift_height_m: float
    density_kg_m3: float
    friction_pa_per_m3s2: float = 0.0
    intake_offset_pa: float = 0.0
    g: float = STANDARD_GRAVITY

    def __post_init__(self) -> None:
        _finite("reservoir_pressure_pa", self.reservoir_pressure_pa, minimum=0, strict=True)
        _finite(
            "productivity_index_m3_s_per_pa",
            self.productivity_index_m3_s_per_pa,
            minimum=0,
            strict=True,
        )  # noqa: E501
        _finite("wellhead_pressure_pa", self.wellhead_pressure_pa, minimum=0)
        _finite("lift_height_m", self.lift_height_m, minimum=0)
        _finite("density_kg_m3", self.density_kg_m3, minimum=0, strict=True)
        _finite("friction_pa_per_m3s2", self.friction_pa_per_m3s2, minimum=0)
        _finite("intake_offset_pa", self.intake_offset_pa, minimum=0)
        if self.intake_offset_pa >= self.reservoir_pressure_pa:
            raise ValueError("intake_offset_pa must be below the reservoir pressure")

    @property
    def max_flow_m3_s(self) -> float:
        """Flow at which the intake pressure would reach zero (absolute)."""
        return self.productivity_index_m3_s_per_pa * (
            self.reservoir_pressure_pa - self.intake_offset_pa
        )

    def intake_pressure_pa(self, flow_m3_s: float) -> float:
        q = _finite("flow_m3_s", flow_m3_s, minimum=0)
        return (
            self.reservoir_pressure_pa
            - q / self.productivity_index_m3_s_per_pa
            - self.intake_offset_pa
        )  # noqa: E501

    def discharge_pressure_pa(self, flow_m3_s: float) -> float:
        q = _finite("flow_m3_s", flow_m3_s, minimum=0)
        rho_g = self.density_kg_m3 * self.g
        return (
            self.wellhead_pressure_pa
            + rho_g * self.lift_height_m
            + self.friction_pa_per_m3s2 * q**2
        )  # noqa: E501

    def required_head_m(self, flow_m3_s: float) -> float:
        dp = self.discharge_pressure_pa(flow_m3_s) - self.intake_pressure_pa(flow_m3_s)
        return dp / (self.density_kg_m3 * self.g)


class OperatingPointError(ValueError):
    """The pump curve and the system curve do not intersect in the valid range."""


@dataclass(frozen=True)
class OperatingPointResult:
    operating_point: OperatingPoint
    intake_pressure_pa: float
    discharge_pressure_pa: float
    relative_flow: float | None  # Q / Q_BEP at this speed
    in_operating_range: bool | None


def solve_operating_point(
    pump: PumpCurve, system: WellSystem, speed_rpm: float, temperature_c: float | None = None
) -> OperatingPointResult:
    """Intersection of the speed-scaled pump curve with the well's system curve.

    Raises :class:`OperatingPointError` when there is no intersection within the
    catalog flow range with positive intake pressure (e.g. speed too low to lift).
    """
    lo, hi = pump.flow_range_m3_s(speed_rpm)
    hi = min(hi, system.max_flow_m3_s * (1 - 1e-9))
    if hi <= lo:
        raise OperatingPointError("catalog flow range lies beyond the well's maximum inflow")

    def residual(q: float) -> float:
        return pump.head_m(q, speed_rpm) - system.required_head_m(q)

    r_lo, r_hi = residual(lo), residual(hi)
    if r_lo < 0:
        have, need = pump.head_m(lo, speed_rpm), system.required_head_m(lo)
        raise OperatingPointError(
            f"at {speed_rpm:g} rpm the pump cannot reach the required head even at the lowest "
            f"catalog flow ({have:.1f} m < {need:.1f} m)"
        )
    if r_hi > 0:
        raise OperatingPointError(
            f"at {speed_rpm:g} rpm the pump would deliver more than the valid range allows "
            "(beyond catalog range or intake pressure would drop to zero)"
        )
    q = float(brentq(residual, lo, hi, xtol=1e-12))
    op = OperatingPoint(
        flow_m3_s=q,
        head_m=pump.head_m(q, speed_rpm),
        speed_rpm=speed_rpm,
        density_kg_m3=system.density_kg_m3,
        temperature_c=temperature_c,
    )
    relative = q / pump.bep_flow_at(speed_rpm) if pump.bep_flow_m3_s is not None else None
    in_range = None
    if pump.operating_range_m3_s is not None:
        r_lo_q, r_hi_q = pump.operating_range_at(speed_rpm)
        in_range = r_lo_q <= q <= r_hi_q
    return OperatingPointResult(
        operating_point=op,
        intake_pressure_pa=system.intake_pressure_pa(q),
        discharge_pressure_pa=system.discharge_pressure_pa(q),
        relative_flow=relative,
        in_operating_range=in_range,
    )
