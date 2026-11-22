"""Paderborn loader tests. All files are invented fixtures (see paderborn_fixtures.py)."""

import numpy as np
import pytest

from paderborn_fixtures import FIXTURE_DURATION_S, write_dataset, write_mat
from pumpguard.datasets.paderborn import (
    BEARING_6203,
    BEARINGS,
    LABELS,
    OPERATING_CONDITIONS,
    TASKS,
    PaderbornError,
    PaderbornFileError,
    PaderbornFormatError,
    build_feature_table,
    inspect_file,
    parse_filename,
    read_measurement,
    scan,
)

D = FIXTURE_DURATION_S

# ------------------------------------------------------------ static metadata


def test_bearing_table_matches_publication_counts():
    origins = [b.damage_origin for b in BEARINGS.values()]
    assert len(BEARINGS) == 32
    assert origins.count("none") == 6
    assert origins.count("artificial") == 12
    assert origins.count("real") == 14


def test_bearing_labels_agree_with_code_prefix():
    prefix = {"K0": "healthy", "KA": "outer", "KI": "inner", "KB": "outer+inner"}
    for code, info in BEARINGS.items():
        assert info.label == prefix[code[:2]], code
        assert info.label in LABELS


def test_operating_conditions():
    assert OPERATING_CONDITIONS["N09_M07_F10"].rpm == 900
    assert OPERATING_CONDITIONS["N15_M01_F10"].load_torque_nm == 0.1
    assert OPERATING_CONDITIONS["N15_M07_F04"].radial_force_n == 400


def test_tasks_are_consistent():
    real3 = TASKS["real3"].bearings
    assert len(real3) == 15
    assert {BEARINGS[c].label for c in real3} == {"healthy", "outer", "inner"}
    assert all(BEARINGS[c].damage_origin != "artificial" for c in real3)
    split = TASKS["artificial_to_real"].split
    assert split is not None
    train = {c for c, s in split.items() if s == "train"}
    test = {c for c, s in split.items() if s == "test"}
    assert train.isdisjoint(test)
    assert all(BEARINGS[c].damage_origin != "real" for c in train)
    assert all(BEARINGS[c].damage_origin != "artificial" for c in test)
    assert all(BEARINGS[c].label != "outer+inner" for c in TASKS["all_single"].bearings)


def test_6203_defect_frequencies():
    f = BEARING_6203.defect_frequencies(1500)
    assert f.bpfo == pytest.approx(76.36, abs=0.05)
    assert f.bpfi == pytest.approx(123.64, abs=0.05)


# ------------------------------------------------------------------ filenames


def test_parse_filename():
    info = parse_filename("some/dir/N09_M07_F10_KI21_17.mat")
    assert info.condition.rpm == 900
    assert info.bearing.code == "KI21"
    assert info.bearing.damage_origin == "real"
    assert info.measurement_index == 17


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("N15_M07_F10_KA01_1.txt", "expected a .mat"),
        ("random.mat", "does not match"),
        ("N12_M07_F10_KA01_1.mat", "unknown operating condition"),
        ("N15_M07_F10_KA99_1.mat", "unknown bearing"),
    ],
)
def test_parse_filename_rejects_bad_names(name, fragment):
    with pytest.raises(PaderbornFormatError, match=fragment):
        parse_filename(name)


# --------------------------------------------------------------- reading files


def test_read_measurement_returns_signal_and_valid_provenance(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_KA04_3.mat", speed_rpm=1493.0)
    m = read_measurement(path, root=tmp_path, expected_duration_s=D, compute_sha256=True)
    assert m.fs == 64_000
    assert m.x.size == int(64_000 * D)
    p = m.provenance
    assert p["synthetic"] is False
    assert p["group_id"] == "KA04"
    assert p["label"] == "outer"
    assert p["damage_origin"] == "real"
    assert p["unit"] == "m/s^2"
    assert p["license"] == "CC BY-NC 4.0"
    assert p["rpm_source"] == "measured_speed_channel"
    assert p["rpm"] == pytest.approx(1493.0, abs=1.0)
    assert len(p["sha256"]) == 64
    assert "pump" in p["machine_type"]  # states explicitly that it is NOT a pump


def test_implausible_speed_channel_falls_back_to_nominal(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_K001_1.mat", speed_rpm=157.0)  # rad/s, say
    m = read_measurement(path, expected_duration_s=D)
    assert m.provenance["rpm_source"] == "nominal_setting"
    assert m.provenance["rpm"] == 1500
    assert "not within" in m.notes[0]


def test_missing_speed_channel_uses_nominal(tmp_path):
    path = write_mat(tmp_path / "N09_M07_F10_K002_1.mat", include_speed=False)
    m = read_measurement(path, expected_duration_s=D)
    assert m.provenance["rpm"] == 900
    assert "no 'speed' channel" in m.notes[0]


def test_measured_speed_can_be_disabled(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_K001_1.mat", speed_rpm=1490.0)
    m = read_measurement(path, expected_duration_s=D, use_measured_speed=False)
    assert m.provenance["rpm_source"] == "nominal_setting"


def test_empty_matlab_unit_field_is_handled(tmp_path):
    # Real Paderborn files store Unit as an empty MATLAB array ([]) for every channel.
    path = write_mat(tmp_path / "N15_M07_F10_KA04_1.mat", vibration_unit=np.zeros((0, 0)))
    m = read_measurement(path, expected_duration_s=D)
    assert m.provenance["unit"] == "unspecified in source"
    rows = {r["name"]: r for r in inspect_file(path)}
    assert rows["vibration_1"]["unit"] == ""
    assert rows["force"]["unit"] == "N"


def test_missing_channel_lists_available_ones(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_K001_1.mat", drop_vibration=True)
    with pytest.raises(PaderbornFormatError, match="available: .*force"):
        read_measurement(path, expected_duration_s=D)


def test_unknown_channel_rate_is_rejected(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_K001_1.mat")
    with pytest.raises(PaderbornFormatError):
        read_measurement(path, channel="nonexistent", expected_duration_s=D)


def test_duration_check_catches_wrong_length(tmp_path):
    path = write_mat(tmp_path / "N15_M07_F10_K001_1.mat")
    with pytest.raises(PaderbornFormatError, match="expected about 4 s"):
        read_measurement(path)  # default expects 4 s recordings
    assert read_measurement(path, expected_duration_s=None).x.size > 0


def test_corrupt_file_raises_file_error(tmp_path):
    path = tmp_path / "N15_M07_F10_KA08_2.mat"
    path.write_bytes(b"MATLAB 5.0 MAT-file, truncated garbage")
    with pytest.raises(PaderbornFileError, match="cannot be read"):
        read_measurement(path)


def test_file_without_channel_records(tmp_path):
    import scipy.io as sio

    path = tmp_path / "N15_M07_F10_K001_1.mat"
    sio.savemat(str(path), {"something": np.arange(5.0)})
    with pytest.raises(PaderbornFormatError, match="no channel records"):
        read_measurement(path)


def test_inspect_file_lists_channels(tmp_path):
    rows = inspect_file(write_mat(tmp_path / "N15_M07_F10_K001_1.mat"))
    names = {r["name"]: r for r in rows}
    assert names["vibration_1"]["n_samples"] == int(64_000 * D)
    assert names["vibration_1"]["documented_fs_hz"] == 64_000
    assert names["speed"]["unit"] == "rpm"


# ------------------------------------------------------- scanning and features


def test_scan_finds_files_recursively_and_reports_unknown(tmp_path):
    write_dataset(tmp_path, ["K001", "KA04"], measurements=2)
    (tmp_path / "notes.mat").write_bytes(b"")
    index, skipped = scan(tmp_path)
    assert len(index) == 4
    assert set(index["bearing"]) == {"K001", "KA04"}
    assert skipped[0]["file"] == "notes.mat"


def test_scan_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan(tmp_path / "nope")


@pytest.fixture(scope="module")
def real3_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("paderborn")
    write_dataset(root, sorted(TASKS["real3"].bearings), measurements=2)
    # one corrupt file and one non-task bearing must not break the run
    (root / "KA04" / "N15_M07_F10_KA04_9.mat").write_bytes(b"corrupt")
    write_dataset(root, ["KA01"], measurements=1)
    return root


def test_feature_table_groups_by_bearing(real3_root):
    df, report = build_feature_table(real3_root, segment_seconds=D / 2, expected_duration_s=D)
    assert len(df) == 15 * 2 * 2  # bearings x measurements x segments
    assert set(df["group_id"]) == TASKS["real3"].bearings
    assert df.groupby("group_id")["label"].nunique().max() == 1
    assert not df["synthetic"].any()
    assert "KA01" not in set(df["group_id"])
    assert report["n_files_used"] == 30
    assert len(report["failures"]) == 1
    assert "KA04_9" in report["failures"][0]["file"]
    assert report["license"] == "CC BY-NC 4.0"
    assert report["missing_bearings"] == []


def test_feature_table_separates_fixture_classes(real3_root):
    df, _ = build_feature_table(real3_root, segment_seconds=D / 2, expected_duration_s=D)
    med = df.groupby("label")[["env_bpfo_ratio", "env_bpfi_ratio"]].median()
    assert med.loc["outer", "env_bpfo_ratio"] > 3 * med.loc["healthy", "env_bpfo_ratio"]
    assert med.loc["inner", "env_bpfi_ratio"] > 3 * med.loc["healthy", "env_bpfi_ratio"]


def test_artificial_to_real_adds_split_column(tmp_path):
    write_dataset(tmp_path, ["K001", "KA01", "K004", "KA04"], measurements=1)
    df, report = build_feature_table(
        tmp_path, task="artificial_to_real", segment_seconds=D, expected_duration_s=D
    )
    split = df.groupby("group_id")["split"].first().to_dict()
    assert split == {"K001": "train", "KA01": "train", "K004": "test", "KA04": "test"}
    assert "KI21" in report["missing_bearings"]


def test_feature_table_filters(real3_root):
    df, _ = build_feature_table(
        real3_root, segment_seconds=D, expected_duration_s=D, max_measurements=1
    )
    assert set(df["acquisition_id"].str[-1]) == {"1"}
    with pytest.raises(ValueError, match="operating condition"):
        build_feature_table(real3_root, conditions=["N99_M07_F10"])
    with pytest.raises(ValueError, match="task"):
        build_feature_table(real3_root, task="nope")
    with pytest.raises(ValueError, match="segment_seconds"):
        build_feature_table(real3_root, segment_seconds=0)


def test_no_usable_files_gives_actionable_error(tmp_path):
    write_dataset(tmp_path, ["KA01"], measurements=1)  # not part of real3
    with pytest.raises(PaderbornError, match="Expected files such as"):
        build_feature_table(tmp_path, expected_duration_s=D)
