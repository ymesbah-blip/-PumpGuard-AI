import json

import numpy as np
import pytest

from pumpguard import CONDITIONS, SignalConfig, generate_signal, simulate
from pumpguard.features import extract_features


@pytest.mark.parametrize("condition", CONDITIONS)
def test_shape_and_finiteness(condition, signals):
    sig = signals[condition]
    assert sig.t.shape == sig.x.shape == (24_000,)
    assert np.all(np.isfinite(sig.x))
    assert sig.t[1] - sig.t[0] == pytest.approx(1 / 12_000)


@pytest.mark.parametrize("condition", CONDITIONS)
def test_same_seed_is_reproducible(condition):
    a = simulate(SignalConfig(condition=condition, seed=7, duration=0.5)).x
    b = simulate(SignalConfig(condition=condition, seed=7, duration=0.5)).x
    np.testing.assert_array_equal(a, b)


def test_different_seeds_differ():
    a = simulate(SignalConfig(seed=1, duration=0.5)).x
    b = simulate(SignalConfig(seed=2, duration=0.5)).x
    assert not np.allclose(a, b)


@pytest.mark.parametrize("condition", [c for c in CONDITIONS if c != "healthy"])
def test_zero_severity_reproduces_healthy(condition):
    healthy = simulate(SignalConfig(condition="healthy", seed=3, duration=0.5)).x
    zero = simulate(SignalConfig(condition=condition, severity=0.0, seed=3, duration=0.5)).x
    np.testing.assert_array_equal(healthy, zero)


def test_fault_energy_grows_with_severity():
    rms = [
        extract_features(simulate(SignalConfig(condition="imbalance", severity=s)).x)["rms"]
        for s in (0.0, 0.5, 1.0, 2.0)
    ]
    assert rms == sorted(rms)


def test_generate_signal_backward_compatible_signature():
    t, x = generate_signal("imbalance", fs=2000, duration=2.0, rpm=1800, seed=42)
    assert t.shape == x.shape == (4000,)


def test_bearing_like_alias_warns_and_maps_to_outer():
    with pytest.warns(DeprecationWarning, match="bearing_outer"):
        cfg = SignalConfig(condition="bearing_like", duration=0.5)
    assert cfg.condition == "bearing_outer"
    np.testing.assert_array_equal(
        simulate(cfg).x, simulate(SignalConfig(condition="bearing_outer", duration=0.5)).x
    )


def test_resonance_auto_scales_with_low_fs():
    cfg = SignalConfig(condition="bearing_outer", fs=2000, rpm=1800)
    assert cfg.resolved_resonance_hz < cfg.fs / 2
    assert np.all(np.isfinite(simulate(cfg).x))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"condition": "broken"}, "condition"),
        ({"fs": 0}, "fs"),
        ({"duration": -1}, "duration"),
        ({"rpm": float("nan")}, "rpm"),
        ({"fs": 100, "duration": 0.5}, "samples"),
        ({"noise_std": -0.1}, "noise_std"),
        ({"severity": -1}, "severity"),
        ({"n_vanes": 0}, "n_vanes"),
        ({"damping_ratio": 1.5}, "damping_ratio"),
        ({"slip": 0.5}, "slip"),
        ({"fs": 1000, "rpm": 6000}, "alias"),
        ({"resonance_hz": 5900}, "resonance_hz"),
    ],
)
def test_invalid_config_raises(kwargs, message):
    with pytest.raises(ValueError, match=message):
        SignalConfig(**kwargs)


def test_metadata_is_json_and_marked_synthetic(signals):
    meta = signals["bearing_inner"].metadata()
    assert meta["synthetic"] is True
    assert meta["condition"] == "bearing_inner"
    freqs = meta["characteristic_frequencies_hz"]
    assert freqs["bpfi"] == pytest.approx(5.4152 * 30, rel=1e-3)
    json.dumps(meta)  # must not raise


def test_impacts_are_not_quantised_to_sample_grid(signals, bearing):
    """v0.1 rounded the impact interval to whole samples (133 Hz instead of 126 Hz)."""
    from pumpguard.spectral import envelope_spectrum

    freqs, amp = envelope_spectrum(signals["bearing_outer"].x, 12_000)
    window = (freqs > 50) & (freqs < 150)
    peak_hz = freqs[window][np.argmax(amp[window])]
    assert peak_hz == pytest.approx(bearing.defect_frequencies(1800).bpfo, abs=1.0)
