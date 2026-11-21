"""Synthetic operating-regime sweeps for a multistage pump in a well.

Everything here is **synthetic and illustrative**: the default pump curve and
well are invented for teaching, not taken from any catalog or field. Use your
own :class:`~pumpguard.hydraulics.PumpCurve` (from the manufacturer's catalog)
and :class:`~pumpguard.hydraulics.WellSystem` (from well data) for real studies.

Two sweeps:

* :func:`speed_sweep`: for each speed, solve the intersection of the pump curve
  with the well's system curve (physically consistent operating points).
* :func:`flow_speed_grid`: the pump alone over a grid of speed x flow (what the
  curve family says, independent of any system).

:func:`naive_affinity_projection` reproduces the common shortcut "Q ~ N,
dp ~ N^2 from one measured point" so that its error against the consistent
solution can be shown. It is not a model to use.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from .hydraulics import (
    OperatingPointError,
    PumpCurve,
    WellSystem,
    hydraulic_power_w,
    solve_operating_point,
)
from .orders import shaft_hz, vane_pass_hz
from .units import bar_to_pa, bpd_to_m3s, ft_to_m, m3s_to_bpd

__all__ = [
    "flow_speed_grid",
    "illustrative_esp",
    "illustrative_well",
    "naive_affinity_projection",
    "speed_sweep",
]


def illustrative_esp(n_stages: int = 250) -> PumpCurve:
    """Invented 1200-BPD-class ESP stage curve at 3600 rpm (NOT a manufacturer curve)."""
    q_bpd = (0, 300, 600, 900, 1200, 1500, 1800, 2000)
    h_ft = (20.5, 20.1, 19.1, 17.6, 15.6, 13.1, 10.0, 7.6)
    return PumpCurve(
        flow_m3_s=tuple(bpd_to_m3s(q) for q in q_bpd),
        head_m_per_stage=tuple(ft_to_m(h) for h in h_ft),
        reference_speed_rpm=3600.0,
        n_stages=n_stages,
        degree=3,
        bep_flow_m3_s=bpd_to_m3s(1200),
        operating_range_m3_s=(bpd_to_m3s(900), bpd_to_m3s(1500)),
        name="illustrative ESP stage",
        source="invented for PumpGuard examples; not a catalog curve",
    )


def illustrative_well() -> WellSystem:
    """Invented well: 90 bar reservoir, PI 30 BPD/bar, 1500 m lift, 10 bar wellhead."""
    return WellSystem(
        reservoir_pressure_pa=bar_to_pa(90.0),
        productivity_index_m3_s_per_pa=bpd_to_m3s(30.0) / bar_to_pa(1.0),
        wellhead_pressure_pa=bar_to_pa(10.0),
        lift_height_m=1500.0,
        density_kg_m3=950.0,
        friction_pa_per_m3s2=bar_to_pa(4.0) / bpd_to_m3s(1000.0) ** 2,
    )


def speed_sweep(
    pump: PumpCurve,
    system: WellSystem,
    speeds_rpm: Iterable[float],
    *,
    n_vanes: int | None = None,
) -> pd.DataFrame:
    """Solve the operating point at each speed. Infeasible speeds are kept with a note."""
    rows = []
    for speed in speeds_rpm:
        row: dict[str, object] = {"speed_rpm": float(speed), "shaft_hz": shaft_hz(speed)}
        if n_vanes is not None:
            row["vane_pass_hz"] = vane_pass_hz(speed, n_vanes)
        try:
            res = solve_operating_point(pump, system, speed)
        except OperatingPointError as exc:
            row.update(feasible=False, note=str(exc))
        else:
            op = res.operating_point
            row.update(
                feasible=True,
                note="",
                flow_m3_s=op.flow_m3_s,
                flow_bpd=m3s_to_bpd(op.flow_m3_s),
                head_m=op.head_m,
                intake_pressure_pa=res.intake_pressure_pa,
                discharge_pressure_pa=res.discharge_pressure_pa,
                hydraulic_power_w=op.hydraulic_power_w,
                relative_flow=res.relative_flow,
                in_operating_range=res.in_operating_range,
            )
        row["synthetic"] = True
        rows.append(row)
    return pd.DataFrame(rows)


def flow_speed_grid(
    pump: PumpCurve,
    speeds_rpm: Sequence[float],
    flow_fractions: Sequence[float] = tuple(np.linspace(0.0, 1.0, 11)),
    *,
    density_kg_m3: float = 1000.0,
) -> pd.DataFrame:
    """Pump-only grid: each speed x fraction of that speed's catalog flow range."""
    if any(not 0.0 <= f <= 1.0 for f in flow_fractions):
        raise ValueError("flow_fractions must lie in [0, 1]")
    rows = []
    for speed in speeds_rpm:
        lo, hi = pump.flow_range_m3_s(speed)
        for frac in flow_fractions:
            q = lo + frac * (hi - lo)
            h = pump.head_m(q, speed)
            row = {
                "speed_rpm": float(speed),
                "flow_m3_s": q,
                "flow_bpd": m3s_to_bpd(q),
                "head_m": h,
                "hydraulic_power_w": hydraulic_power_w(q, h, density_kg_m3),
                "synthetic": True,
            }
            if pump.bep_flow_m3_s is not None:
                row["relative_flow"] = q / pump.bep_flow_at(speed)
            if pump.operating_range_m3_s is not None:
                r_lo, r_hi = pump.operating_range_at(speed)
                row["in_operating_range"] = bool(r_lo <= q <= r_hi)
            rows.append(row)
    return pd.DataFrame(rows)


def naive_affinity_projection(
    pump: PumpCurve,
    system: WellSystem,
    reference_speed_rpm: float,
    speeds_rpm: Iterable[float],
) -> pd.DataFrame:
    """Compare "Q ~ N, dp ~ N^2 from one point" with the consistent intersection.

    Columns ``*_naive`` come from scaling the solved reference point; ``*_solved``
    from solving at each speed. ``system_head_gap_m`` is how far the naive point
    is from satisfying the well's system curve (zero for a consistent point).
    """
    ref = solve_operating_point(pump, system, reference_speed_rpm).operating_point
    rows = []
    for speed in speeds_rpm:
        r = float(speed) / reference_speed_rpm
        q_naive, h_naive = ref.flow_m3_s * r, ref.head_m * r**2
        row: dict[str, object] = {
            "speed_rpm": float(speed),
            "flow_bpd_naive": m3s_to_bpd(q_naive),
            "head_m_naive": h_naive,
            "system_head_gap_m": h_naive
            - system.required_head_m(min(q_naive, system.max_flow_m3_s)),
        }
        try:
            solved = solve_operating_point(pump, system, speed).operating_point
            row.update(flow_bpd_solved=m3s_to_bpd(solved.flow_m3_s), head_m_solved=solved.head_m)
            row["flow_error_pct"] = 100.0 * (q_naive - solved.flow_m3_s) / solved.flow_m3_s
        except OperatingPointError as exc:
            row.update(flow_bpd_solved=np.nan, head_m_solved=np.nan, flow_error_pct=np.nan,
                       note=str(exc))  # fmt: skip
        rows.append(row)
    return pd.DataFrame(rows)
