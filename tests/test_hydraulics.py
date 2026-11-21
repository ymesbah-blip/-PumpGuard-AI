"""Exact and property tests for units, hydraulics and the operating-point solver."""

import numpy as np
import pytest

from pumpguard.hydraulics import (
    OperatingPoint,
    OperatingPointError,
    PumpCurve,
    WellSystem,
    affinity_scale,
    head_from_pressure,
    hydraulic_power_w,
    npsh_available_m,
    pressure_from_head,
    solve_operating_point,
)
from pumpguard.regime import illustrative_esp, illustrative_well
from pumpguard.units import (
    STANDARD_GRAVITY,
    bar_to_pa,
    bpd_to_m3s,
    celsius_to_kelvin,
    ft_to_m,
    m3s_to_bpd,
    m_to_ft,
    pa_to_bar,
    pa_to_psi,
    psi_to_pa,
)

G = STANDARD_GRAVITY

# --------------------------------------------------------------------- units


def test_unit_conversions_exact():
    assert bpd_to_m3s(1.0) == pytest.approx(0.158987294928 / 86_400, rel=1e-15)
    assert pytest.approx(6.2898, abs=1e-4) == 1.0 / 0.158987294928  # bbl per m^3
    assert m3s_to_bpd(bpd_to_m3s(961.1)) == pytest.approx(961.1, rel=1e-14)
    assert ft_to_m(1.0) == 0.3048
    assert m_to_ft(ft_to_m(15.99)) == pytest.approx(15.99, rel=1e-14)
    assert bar_to_pa(75.52) == pytest.approx(7.552e6, rel=1e-14)
    assert pa_to_bar(1e5) == 1.0
    assert pa_to_psi(bar_to_pa(1.0)) == pytest.approx(14.503773773, rel=1e-9)
    assert psi_to_pa(1.0) == pytest.approx(6894.757293168, rel=1e-12)
    assert celsius_to_kelvin(0.0) == 273.15
    with pytest.raises(ValueError, match="absolute zero"):
        celsius_to_kelvin(-300.0)


# --------------------------------------------------------------- hydraulics


def test_head_and_pressure_exact():
    assert head_from_pressure(G * 1000.0, 1000.0) == pytest.approx(1.0, rel=1e-15)
    assert pressure_from_head(1.0, 1000.0) == pytest.approx(G * 1000.0, rel=1e-15)
    # TDH = dp / (rho_w g SG) as in an ESP surveillance calculation (g = 9.81 there)
    assert head_from_pressure(bar_to_pa(75.52), 1156.0, g=9.81) == pytest.approx(
        7.552e6 / (1156.0 * 9.81), rel=1e-15
    )
    with pytest.raises(ValueError, match="density"):
        head_from_pressure(1e5, 0.0)


def test_hydraulic_power_exact():
    assert hydraulic_power_w(0.01, 100.0, 1000.0) == pytest.approx(1000.0 * G, rel=1e-15)
    with pytest.raises(ValueError, match="flow"):
        hydraulic_power_w(-0.01, 100.0, 1000.0)


def test_affinity_scale_exact():
    q, h, p = affinity_scale(1.0, 10.0, 100.0, 3000.0, 3600.0)
    assert (q, h, p) == pytest.approx((1.2, 14.4, 172.8), rel=1e-14)
    assert affinity_scale(1.0, 10.0, None, 3000.0, 3600.0)[2] is None
    with pytest.raises(ValueError, match="speed"):
        affinity_scale(1.0, 10.0, None, 0.0, 3600.0)


def test_npsh_available_exact():
    expected = (2e5 - 2339.0) / (998.2 * G) + 1.5**2 / (2 * G)
    assert npsh_available_m(2e5, 2339.0, 998.2, velocity_m_s=1.5) == pytest.approx(expected)


def test_operating_point_derived_quantities():
    op = OperatingPoint(0.01, 100.0, 3000.0, 1000.0, temperature_c=60.0, shaft_power_w=2000.0 * G,
                        npsh_available_m=12.0, npsh_required_m=4.5)  # fmt: skip
    assert op.shaft_hz == 50.0
    assert op.hydraulic_power_w == pytest.approx(1000.0 * G)
    assert op.efficiency == pytest.approx(0.5)
    assert op.npsh_margin_m == pytest.approx(7.5)
    bare = OperatingPoint(0.01, 100.0, 3000.0, 1000.0)
    assert bare.efficiency is None
    assert bare.npsh_margin_m is None


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"flow_m3_s": -1.0}, "flow"),
        ({"head_m": float("nan")}, "head"),
        ({"speed_rpm": 0.0}, "speed"),
        ({"density_kg_m3": -5.0}, "density"),
        ({"temperature_c": -400.0}, "temperature"),
        ({"shaft_power_w": 100.0}, "exceeds shaft power"),
        ({"npsh_available_m": float("inf")}, "npsh"),
    ],
)
def test_operating_point_validation(kwargs, fragment):
    base = {"flow_m3_s": 0.01, "head_m": 100.0, "speed_rpm": 3000.0, "density_kg_m3": 1000.0}
    with pytest.raises(ValueError, match=fragment):
        OperatingPoint(**{**base, **kwargs})


# --------------------------------------------------------------- pump curve


def _cubic_pump(**kw):
    q = np.linspace(0.0, 0.005, 9)
    h = 20.0 - 1000.0 * q - 5e5 * q**2  # monotonically decreasing, 2.5 m at the last point
    args = {"reference_speed_rpm": 3600.0, "n_stages": 10, "degree": 3}
    args.update(kw)
    return PumpCurve(tuple(q), tuple(h), **args)


def test_pump_curve_recovers_exact_polynomial():
    pump = _cubic_pump()
    assert pump.rmse_m < 1e-10
    assert pump.stage_head_m(0.003, 3600.0) == pytest.approx(20.0 - 3.0 - 4.5, rel=1e-10)
    assert pump.head_m(0.003, 3600.0) == pytest.approx(10 * 12.5, rel=1e-10)


@pytest.mark.parametrize("ratio", [0.6, 0.8, 1.0, 1.25])
def test_affinity_property_of_curve(ratio):
    pump = _cubic_pump()
    for q in (0.0, 0.002, 0.0045):
        scaled = pump.stage_head_m(q * ratio, 3600.0 * ratio)
        assert scaled == pytest.approx(ratio**2 * pump.stage_head_m(q, 3600.0), rel=1e-12)
    lo, hi = pump.flow_range_m3_s(3600.0 * ratio)
    assert (lo, hi) == pytest.approx((0.0, 0.005 * ratio))


def test_inversion_round_trip():
    pump = _cubic_pump()
    for speed in (2400.0, 3000.0, 3600.0):
        for q in np.linspace(0.0005, 0.9 * pump.flow_range_m3_s(speed)[1], 5):
            h = pump.head_m(q, speed)
            assert pump.flow_at_head(h, speed) == pytest.approx(q, abs=1e-10)
    lo, hi = pump.flow_range_m3_s(3600.0)
    assert pump.flow_at_head(pump.head_m(lo, 3600.0), 3600.0) == lo
    assert pump.flow_at_head(pump.head_m(hi, 3600.0), 3600.0) == hi


def test_bep_and_operating_range_scale_linearly():
    pump = _cubic_pump(bep_flow_m3_s=0.004, operating_range_m3_s=(0.003, 0.005))
    assert pump.bep_flow_at(1800.0) == pytest.approx(0.002)
    assert pump.operating_range_at(1800.0) == pytest.approx((0.0015, 0.0025))


@pytest.mark.parametrize(
    ("q", "h", "kw", "fragment"),
    [
        ((0.0, 0.001, 0.002), (5.0, 4.0, 3.0), {}, "at least"),
        ((0.0, 0.002, 0.001, 0.003, 0.004), (5, 4, 4.5, 3, 2), {}, "strictly increasing"),
        ((0.0, 0.001, 0.002, 0.003, 0.004), (5, 4, 3, 2, 0), {}, "> 0"),
        ((0.0, 0.001, 0.002, 0.003, 0.004), (3, 4, 5, 4.5, 4), {}, "rises"),
        ((0.0, 0.001, 0.002, 0.003, 0.004), (5, 4, 3, 2, 1), {"bep_flow_m3_s": 0.01}, "bep"),
        ((0.0, 0.001, 0.002, 0.003, 0.004), (5, 4, 3, 2, 1), {"n_stages": 0}, "n_stages"),
    ],
)
def test_pump_curve_validation(q, h, kw, fragment):
    with pytest.raises(ValueError, match=fragment):
        PumpCurve(q, h, 3600.0, **kw)


def test_no_extrapolation_and_head_range_checks():
    pump = _cubic_pump()
    with pytest.raises(ValueError, match="outside catalog range"):
        pump.stage_head_m(0.007, 3600.0)
    with pytest.raises(ValueError, match="outside"):
        pump.flow_at_head(1e6, 3600.0)
    with pytest.raises(ValueError, match="not provided"):
        pump.bep_flow_at(3600.0)
    with pytest.raises(ValueError, match="not provided"):
        pump.operating_range_at(3600.0)


# ------------------------------------------------------- well and solver


def test_well_system_exact():
    well = WellSystem(bar_to_pa(90), bpd_to_m3s(30) / 1e5, bar_to_pa(10), 1500.0, 950.0,
                      friction_pa_per_m3s2=2e9, intake_offset_pa=bar_to_pa(5))  # fmt: skip
    q = bpd_to_m3s(600)
    assert well.intake_pressure_pa(q) == pytest.approx(bar_to_pa(90 - 20 - 5))
    assert well.discharge_pressure_pa(q) == pytest.approx(1e6 + 950 * G * 1500 + 2e9 * q**2)
    expected = (well.discharge_pressure_pa(q) - well.intake_pressure_pa(q)) / (950 * G)
    assert well.required_head_m(q) == pytest.approx(expected)
    assert well.max_flow_m3_s == pytest.approx(bpd_to_m3s(30) / 1e5 * bar_to_pa(85))
    with pytest.raises(ValueError, match="intake_offset"):
        WellSystem(1e5, 1e-8, 0.0, 10.0, 1000.0, intake_offset_pa=2e5)


def test_solved_point_lies_on_both_curves():
    pump, well = illustrative_esp(), illustrative_well()
    for speed in (2700.0, 3000.0, 3300.0, 3600.0):
        res = solve_operating_point(pump, well, speed, temperature_c=70.0)
        q = res.operating_point.flow_m3_s
        assert pump.head_m(q, speed) == pytest.approx(well.required_head_m(q), abs=1e-6)
        assert res.intake_pressure_pa == pytest.approx(well.intake_pressure_pa(q))
        assert res.operating_point.temperature_c == 70.0


def test_more_speed_gives_more_flow_and_lower_intake_pressure():
    pump, well = illustrative_esp(), illustrative_well()
    speeds = np.linspace(2500.0, 3600.0, 12)
    results = [solve_operating_point(pump, well, s) for s in speeds]
    flows = [r.operating_point.flow_m3_s for r in results]
    intakes = [r.intake_pressure_pa for r in results]
    assert np.all(np.diff(flows) > 0)
    assert np.all(np.diff(intakes) < 0)


def test_with_static_lift_flow_is_not_proportional_to_speed():
    pump, well = illustrative_esp(), illustrative_well()
    q50 = solve_operating_point(pump, well, 3000.0).operating_point.flow_m3_s
    q60 = solve_operating_point(pump, well, 3600.0).operating_point.flow_m3_s
    assert q60 / q50 > 1.3  # far from the naive 3600/3000 = 1.2


def test_infeasible_speeds_raise_clear_errors():
    pump, well = illustrative_esp(), illustrative_well()
    with pytest.raises(OperatingPointError, match="cannot reach the required head"):
        solve_operating_point(pump, well, 1800.0)
    shallow = WellSystem(bar_to_pa(90), bpd_to_m3s(30) / 1e5, bar_to_pa(1), 50.0, 950.0)
    with pytest.raises(OperatingPointError, match="more than the valid range"):
        solve_operating_point(pump, shallow, 3600.0)
    tiny_inflow = WellSystem(bar_to_pa(5), bpd_to_m3s(0.0001) / 1e5, 0.0, 10.0, 950.0)
    with pytest.raises(OperatingPointError, match="maximum inflow"):
        solve_operating_point(
            PumpCurve((0.001, 0.002, 0.003, 0.004, 0.005), (5, 4, 3, 2, 1), 3600.0, degree=2),
            tiny_inflow,
            3600.0,
        )


def test_relative_flow_and_range_flags():
    res = solve_operating_point(illustrative_esp(), illustrative_well(), 3600.0)
    assert res.relative_flow == pytest.approx(
        res.operating_point.flow_m3_s / bpd_to_m3s(1200), rel=1e-12
    )
    assert res.in_operating_range is True
    plain = _cubic_pump()
    well = WellSystem(bar_to_pa(5), bpd_to_m3s(2000) / 1e5, 0.0, 150.0, 1000.0)
    r = solve_operating_point(plain, well, 3600.0)
    assert r.relative_flow is None
    assert r.in_operating_range is None
