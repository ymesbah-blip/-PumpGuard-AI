import pytest

from pumpguard.datasets.provenance import REQUIRED_FIELDS, ProvenanceError, validate_provenance


def _record(**overrides):
    base = {
        "dataset_id": "example",
        "source_url": "https://example.org/data",
        "license": "CC BY 4.0",
        "citation": "Doe (2026)",
        "synthetic": False,
        "source_file": "run1.csv",
        "acquisition_id": "run1",
        "group_id": "machine-A",
        "machine_type": "test rig",
        "sensor": "accelerometer",
        "sensor_location": "bearing housing, radial",
        "channel": "acc_1",
        "unit": "m/s^2",
        "calibration": "none applied",
        "fs_hz": 25_600.0,
        "duration_s": 10.0,
        "rpm": 1480.0,
        "rpm_source": "tachometer",
        "operating_condition": "nominal",
        "label": "healthy",
        "label_method": "visual inspection after test",
        "damage_origin": "none",
    }
    base.update(overrides)
    return base


def test_valid_record_passes_and_is_copied():
    rec = _record()
    out = validate_provenance(rec)
    assert out == rec
    assert out is not rec


def test_all_missing_fields_are_reported_at_once():
    with pytest.raises(ProvenanceError) as exc:
        validate_provenance({"dataset_id": "x"})
    assert len(exc.value.problems) == len(REQUIRED_FIELDS) - 1
    assert "missing 'license'" in str(exc.value)


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"fs_hz": 0}, "fs_hz"),
        ({"rpm": float("nan")}, "rpm"),
        ({"fs_hz": True}, "fs_hz"),
        ({"fs_hz": "25600"}, "fs_hz"),
        ({"license": "  "}, "empty"),
        ({"rpm_source": "guessed"}, "rpm_source"),
        ({"damage_origin": "aliens"}, "damage_origin"),
        ({"synthetic": "no"}, "synthetic"),
        ({"damage_origin": "synthetic"}, "measured record"),
        ({"synthetic": True}, "synthetic records"),
    ],
)
def test_invalid_values_are_explained(override, fragment):
    with pytest.raises(ProvenanceError, match=fragment):
        validate_provenance(_record(**override))


def test_allowed_labels_are_enforced():
    with pytest.raises(ProvenanceError, match="label"):
        validate_provenance(_record(label="broken"), allowed_labels=frozenset({"healthy"}))


def test_consistent_synthetic_record_passes():
    validate_provenance(_record(synthetic=True, damage_origin="synthetic", rpm_source="synthetic"))


def test_error_names_the_record():
    with pytest.raises(ProvenanceError, match="run1"):
        validate_provenance(_record(fs_hz=-1))
