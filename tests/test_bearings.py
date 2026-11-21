import pytest

from pumpguard.bearings import BEARING_PRESETS, BearingGeometry


def test_6205_defect_factors(bearing):
    # Factors per unit shaft frequency from the kinematic formulas.
    f = bearing.defect_frequencies(rpm=60.0)  # 1 Hz shaft
    assert f.shaft_hz == pytest.approx(1.0)
    assert f.bpfo == pytest.approx(3.5848, abs=1e-3)
    assert f.bpfi == pytest.approx(5.4152, abs=1e-3)
    assert f.ftf == pytest.approx(0.3983, abs=1e-3)
    assert f.bsf == pytest.approx(2.3567, abs=1e-3)


def test_kinematic_identities(bearing):
    f = bearing.defect_frequencies(rpm=1750.0)
    assert f.bpfo + f.bpfi == pytest.approx(bearing.n_elements * f.shaft_hz)
    assert f.bpfo == pytest.approx(bearing.n_elements * f.ftf)


def test_frequencies_scale_linearly_with_speed(bearing):
    slow, fast = bearing.defect_frequencies(900), bearing.defect_frequencies(1800)
    for key, value in slow.as_dict().items():
        assert fast.as_dict()[key] == pytest.approx(2 * value)


def test_contact_angle_moves_bpfo_up():
    base = BearingGeometry(9, 8.0, 40.0, 0.0)
    angled = BearingGeometry(9, 8.0, 40.0, 30.0)
    assert angled.defect_frequencies(1800).bpfo > base.defect_frequencies(1800).bpfo


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_elements": 0, "ball_diameter_mm": 8, "pitch_diameter_mm": 40},
        {"n_elements": 9, "ball_diameter_mm": -1, "pitch_diameter_mm": 40},
        {"n_elements": 9, "ball_diameter_mm": 40, "pitch_diameter_mm": 40},
        {"n_elements": 9, "ball_diameter_mm": 8, "pitch_diameter_mm": 40, "contact_angle_deg": 90},
    ],
)
def test_invalid_geometry_raises(kwargs):
    with pytest.raises(ValueError, match=r"n_elements|diameter|contact_angle"):
        BearingGeometry(**kwargs)


def test_unknown_preset_lists_available():
    with pytest.raises(ValueError, match="6205"):
        BearingGeometry.from_preset("nope")


def test_presets_are_valid_geometries():
    for name, geom in BEARING_PRESETS.items():
        assert BearingGeometry.from_preset(name) is geom
        assert geom.defect_frequencies(1800).bpfi > 0


def test_rpm_must_be_positive(bearing):
    with pytest.raises(ValueError, match="rpm"):
        bearing.defect_frequencies(0)
