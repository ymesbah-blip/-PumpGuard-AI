"""Mechanism (orders) and sensor functions are tested separately, by design."""

import numpy as np
import pytest

from pumpguard.orders import (
    characteristic_frequencies,
    rpm_from_supply_frequency,
    shaft_hz,
    vane_pass_hz,
)
from pumpguard.sensors import (
    SensorSpec,
    acceleration_from_voltage,
    measure,
    minimum_sample_rate_hz,
    resolvable,
    sampling_report,
)

# ------------------------------------------------------------------- orders


def test_orders_exact():
    assert shaft_hz(3600.0) == 60.0
    assert rpm_from_supply_frequency(60.0) == 3600.0
    assert rpm_from_supply_frequency(44.0) == pytest.approx(2640.0)
    assert rpm_from_supply_frequency(44.0, slip=0.03) == pytest.approx(2560.8)
    assert rpm_from_supply_frequency(50.0, poles=4) == 1500.0
    assert vane_pass_hz(3000.0, 7) == pytest.approx(350.0)
    assert vane_pass_hz(3000.0, 7, harmonic=2) == pytest.approx(700.0)


def test_characteristic_frequencies():
    f = characteristic_frequencies(1800.0, n_vanes=5, harmonics=2)
    assert f == pytest.approx({"1x": 30.0, "2x": 60.0, "vane_pass_1": 150.0, "vane_pass_2": 300.0})
    assert set(characteristic_frequencies(1800.0)) == {"1x", "2x", "3x"}


@pytest.mark.parametrize(
    ("call", "fragment"),
    [
        (lambda: shaft_hz(0), "rpm"),
        (lambda: rpm_from_supply_frequency(50, poles=3), "poles"),
        (lambda: rpm_from_supply_frequency(50, slip=0.5), "slip"),
        (lambda: vane_pass_hz(3000, 0), "n_vanes"),
        (lambda: vane_pass_hz(3000, 7, harmonic=0), "harmonic"),
        (lambda: characteristic_frequencies(3000, harmonics=0), "harmonics"),
    ],
)
def test_order_validation(call, fragment):
    with pytest.raises(ValueError, match=fragment):
        call()


# ------------------------------------------------------------------ sensors


def test_one_minute_scada_cannot_observe_any_mechanical_order():
    scada = SensorSpec.from_interval(60.0, quantity="acceleration", unit="g")
    assert scada.nyquist_hz == pytest.approx(1 / 120)
    freqs = characteristic_frequencies(rpm_from_supply_frequency(44.0), n_vanes=7)
    rows = sampling_report(scada, freqs)
    assert all(not r["observable"] for r in rows)
    assert "Nyquist" in rows[0]["reason"]


def test_lab_accelerometer_observes_vane_pass_but_respects_cutoff():
    acc = SensorSpec("acceleration", "m/s^2", 25_600.0, anti_alias_cutoff_hz=10_000.0,
                     sensitivity=100.0, sensitivity_unit="mV/g")  # fmt: skip
    assert resolvable(acc, vane_pass_hz(3600.0, 7)) == (True, "observable")
    ok, reason = resolvable(acc, 11_000.0)
    assert not ok
    assert "cutoff" in reason


def test_marginal_sampling_is_flagged():
    spec = SensorSpec("acceleration", "g", 1000.0)
    ok, reason = resolvable(spec, 450.0)  # below Nyquist but fs < 2.56 f
    assert not ok
    assert "2.56" in reason
    assert minimum_sample_rate_hz(1000.0) == pytest.approx(2560.0)


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        ({"sample_rate_hz": 0.0}, "sample_rate"),
        ({"anti_alias_cutoff_hz": 600.0}, "Nyquist"),
        ({"resolution": -1.0}, "resolution"),
        ({"unit": " "}, "required"),
    ],
)
def test_sensor_spec_validation(kwargs, fragment):
    base = {"quantity": "acceleration", "unit": "g", "sample_rate_hz": 1000.0}
    with pytest.raises(ValueError, match=fragment):
        SensorSpec(**{**base, **kwargs})


def test_sensor_helpers_validate():
    with pytest.raises(ValueError, match="sample_interval"):
        SensorSpec.from_interval(0.0, quantity="pressure", unit="bar")
    with pytest.raises(ValueError, match="f_max"):
        minimum_sample_rate_hz(-1.0)
    with pytest.raises(ValueError, match="frequency"):
        resolvable(SensorSpec("pressure", "bar", 10.0), 0.0)


def test_voltage_to_acceleration_exact():
    acc = acceleration_from_voltage([0.1, -0.05], sensitivity_mv_per_g=100.0)
    np.testing.assert_allclose(acc, [9.80665, -4.903325])
    with pytest.raises(ValueError, match="sensitivity"):
        acceleration_from_voltage([0.1], 0.0)


def test_measure_keeps_in_band_and_removes_out_of_band_content():
    fs_in = 10_000.0
    t = np.arange(int(fs_in)) / fs_in
    sensor = SensorSpec("acceleration", "m/s^2", 1000.0, anti_alias_cutoff_hz=400.0)
    low = measure(np.sin(2 * np.pi * 50 * t), fs_in, sensor)
    assert low.size == 1000
    assert np.max(np.abs(low[100:-100])) == pytest.approx(1.0, abs=0.01)
    high = measure(np.sin(2 * np.pi * 3000 * t), fs_in, sensor)  # would alias to 0 Hz without AA
    assert np.max(np.abs(high[100:-100])) < 1e-3


def test_measure_quantises_clips_and_adds_noise():
    spec = SensorSpec("pressure", "bar", 10.0, full_scale=2.0, resolution=0.5)
    out = measure(np.array([0.2, 0.3, 1.1, 5.0, -9.0]), 10.0, spec)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0, 2.0, -2.0])
    noisy = measure(np.zeros(1000), 10.0, SensorSpec("pressure", "bar", 10.0), noise_std=0.1)
    assert np.std(noisy) == pytest.approx(0.1, rel=0.1)
    with pytest.raises(ValueError, match="integer multiple"):
        measure(np.zeros(100), 15.0, SensorSpec("pressure", "bar", 10.0))
    with pytest.raises(ValueError, match="noise_std"):
        measure(np.zeros(100), 10.0, SensorSpec("pressure", "bar", 10.0), noise_std=-1.0)
