import math

import numpy as np
import pytest

from pumpguard.spectral import (
    amplitude_spectrum,
    band_energy_ratio,
    envelope,
    order_amplitudes,
    peak_near,
    spectral_centroid,
    spectral_features,
)

FS = 10_000.0


def _sine(freq, amp=1.0, seconds=1.0):
    t = np.arange(int(FS * seconds)) / FS
    return amp * np.sin(2 * np.pi * freq * t)


def test_amplitude_spectrum_recovers_sine_amplitude():
    freqs, amp = amplitude_spectrum(_sine(120.0, amp=0.7), FS)
    assert freqs[np.argmax(amp)] == pytest.approx(120.0)
    assert amp.max() == pytest.approx(0.7, rel=0.01)


def test_amplitude_spectrum_without_window():
    _, amp = amplitude_spectrum(_sine(100.0, amp=2.0), FS, window=None)
    assert amp.max() == pytest.approx(2.0, rel=1e-6)


def test_amplitude_spectrum_ignores_dc_offset():
    _, amp = amplitude_spectrum(_sine(100.0) + 5.0, FS)
    assert amp[0] == pytest.approx(0.0, abs=1e-9)


def test_peak_near_out_of_range_is_nan():
    freqs, amp = amplitude_spectrum(_sine(50.0), FS)
    assert math.isnan(peak_near(freqs, amp, FS))  # above Nyquist
    assert math.isnan(peak_near(freqs, amp, -1.0))


def test_order_amplitudes_picks_shaft_harmonics():
    x = _sine(30.0, 0.5) + _sine(60.0, 0.2)
    orders = order_amplitudes(x, FS, rpm=1800)
    assert orders["amp_1x"] == pytest.approx(0.5, rel=0.02)
    assert orders["amp_2x"] == pytest.approx(0.2, rel=0.02)
    assert orders["amp_3x"] < 0.01


def test_band_energy_ratio_and_centroid():
    x = _sine(100.0) + _sine(3000.0)
    assert band_energy_ratio(x, FS, 2000, 4000) == pytest.approx(0.5, abs=0.01)
    assert spectral_centroid(x, FS) == pytest.approx(1550.0, rel=0.01)


def test_envelope_of_am_signal_recovers_modulation():
    t = np.arange(int(FS)) / FS
    modulation = 1.0 + 0.5 * np.sin(2 * np.pi * 7 * t)
    env = envelope(modulation * np.sin(2 * np.pi * 2500 * t), FS, band=(1500, 3500))
    core = slice(500, -500)  # ignore filter edges
    np.testing.assert_allclose(env[core], modulation[core], atol=0.05)


@pytest.mark.parametrize("band", [(0, 100), (300, 200), (100, FS)])
def test_envelope_rejects_invalid_band(band):
    with pytest.raises(ValueError, match="band"):
        envelope(_sine(100.0), FS, band=band)


def test_spectral_features_keys_depend_on_inputs(bearing):
    x = _sine(30.0)
    assert set(spectral_features(x, FS)) == {"spectral_centroid_hz", "hf_energy_ratio"}
    with_rpm = spectral_features(x, FS, rpm=1800, n_vanes=5, bearing=bearing)
    assert {"amp_1x", "amp_vane_pass", "env_bpfo_ratio", "env_bpfi_ratio"} <= set(with_rpm)


def test_hf_ratio_nan_when_cutoff_above_nyquist():
    assert math.isnan(spectral_features(_sine(30.0), 1500.0)["hf_energy_ratio"])


# --- the features should separate the synthetic conditions they were designed for ---


def _feats(signals, condition, bearing):
    sig = signals[condition]
    return spectral_features(sig.x, sig.fs, rpm=1800, n_vanes=5, bearing=bearing)


def test_envelope_detects_outer_race_defect(signals, bearing):
    outer = _feats(signals, "bearing_outer", bearing)
    healthy = _feats(signals, "healthy", bearing)
    assert outer["env_bpfo_ratio"] > 10 * healthy["env_bpfo_ratio"]
    assert outer["env_bpfo_ratio"] > 5 * outer["env_bpfi_ratio"]


def test_envelope_detects_inner_race_defect(signals, bearing):
    inner = _feats(signals, "bearing_inner", bearing)
    healthy = _feats(signals, "healthy", bearing)
    assert inner["env_bpfi_ratio"] > 10 * healthy["env_bpfi_ratio"]
    assert inner["env_bpfi_ratio"] > 5 * inner["env_bpfo_ratio"]


def test_orders_separate_imbalance_and_misalignment(signals, bearing):
    imb = _feats(signals, "imbalance", bearing)
    mis = _feats(signals, "misalignment", bearing)
    assert imb["amp_1x"] > 5 * imb["amp_2x"]
    assert mis["amp_2x"] > mis["amp_1x"]


def test_cavitation_raises_high_frequency_energy(signals, bearing):
    cav = _feats(signals, "cavitation_like", bearing)
    healthy = _feats(signals, "healthy", bearing)
    assert cav["hf_energy_ratio"] > 2 * healthy["hf_energy_ratio"]


def test_vane_pass_present_in_every_condition(signals, bearing):
    for condition in signals:
        assert _feats(signals, condition, bearing)["amp_vane_pass"] == pytest.approx(0.06, rel=0.1)
