import math

import numpy as np
import pytest

from pumpguard.features import TIME_FEATURES, demo_health_score, extract_features


def test_features_basic():
    # Original v0.1 test, kept unchanged.
    x = np.array([-1.0, 0.0, 1.0, 0.0])
    f = extract_features(x)
    assert f["rms"] > 0
    assert f["peak"] == 1.0
    assert f["crest_factor"] >= 1.0


def test_returns_documented_keys_in_order():
    f = extract_features(np.sin(np.linspace(0, 10, 500)))
    assert tuple(f) == TIME_FEATURES


def test_pure_sine_matches_analytic_values():
    amplitude, fs, f0 = 2.5, 10_000, 50.0
    t = np.arange(fs) / fs  # exactly 50 periods
    f = extract_features(amplitude * np.sin(2 * np.pi * f0 * t))
    assert f["rms"] == pytest.approx(amplitude / math.sqrt(2), rel=1e-6)
    assert f["peak"] == pytest.approx(amplitude, rel=1e-6)
    assert f["crest_factor"] == pytest.approx(math.sqrt(2), rel=1e-6)
    assert f["kurtosis"] == pytest.approx(1.5, abs=1e-3)  # Pearson kurtosis of a sine
    assert f["skewness"] == pytest.approx(0.0, abs=1e-6)
    assert f["shape_factor"] == pytest.approx(math.pi / (2 * math.sqrt(2)), rel=1e-4)


def test_gaussian_noise_kurtosis_near_three():
    x = np.random.default_rng(0).standard_normal(200_000)
    assert extract_features(x)["kurtosis"] == pytest.approx(3.0, abs=0.05)


def test_impulsive_signal_has_high_kurtosis_and_crest():
    x = np.zeros(10_000)
    x[::500] = 1.0
    f = extract_features(x + 0.01 * np.random.default_rng(1).standard_normal(x.size))
    assert f["kurtosis"] > 50
    assert f["crest_factor"] > 10


def test_constant_signal_gives_nan_for_undefined_moments():
    f = extract_features(np.full(100, 3.0))
    assert f["rms"] == pytest.approx(3.0)
    assert math.isnan(f["kurtosis"])
    assert math.isnan(f["skewness"])


def test_all_zero_signal_gives_nan_ratios():
    f = extract_features(np.zeros(16))
    assert f["rms"] == 0.0
    assert math.isnan(f["crest_factor"])
    assert math.isnan(f["shape_factor"])


@pytest.mark.parametrize(
    "bad",
    [np.array([]), np.zeros((3, 3)), np.array([1.0, np.nan, 2.0]), np.array([1.0, np.inf])],
)
def test_invalid_inputs_raise(bad):
    with pytest.raises(ValueError, match="signal"):
        extract_features(bad)


def test_demo_health_score_bounds_and_monotonic():
    scores = [demo_health_score({"rms": r}) for r in (0.0, 0.1, 0.5, 1.0, 5.0)]
    assert scores[0] == 100.0
    assert scores[-1] == 0.0
    assert scores == sorted(scores, reverse=True)


def test_demo_health_score_rejects_bad_rms():
    with pytest.raises(ValueError, match="rms"):
        demo_health_score({"rms": float("nan")})
