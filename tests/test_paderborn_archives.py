import csv
import hashlib
import json
from pathlib import Path

import pytest

from paderborn_fixtures import FIXTURE_DURATION_S, write_dataset
from pumpguard.cli import main
from pumpguard.datasets.paderborn import BEARINGS, OPERATING_CONDITIONS, TASKS
from pumpguard.datasets.paderborn_archives import (
    VERIFICATION_FILE,
    ZENODO_MANIFEST,
    ArchiveSpec,
    check_inventory,
    load_verification,
    md5sum,
    verify_archives,
    write_verification,
)

REPO = Path(__file__).resolve().parents[1]


def test_manifest_covers_real3_and_documents_the_gap():
    assert TASKS["real3"].bearings <= set(ZENODO_MANIFEST)
    assert set(BEARINGS) - set(ZENODO_MANIFEST) == {"KA08"}
    assert set(ZENODO_MANIFEST) <= set(BEARINGS)
    for code, spec in ZENODO_MANIFEST.items():
        assert spec.name == f"{code}.rar"
        assert len(spec.md5) == 32
        assert int(spec.md5, 16) >= 0
        assert 150e6 < spec.bytes < 200e6
        assert spec.url.endswith(f"/files/{code}.rar?download=1")


def test_windows_script_manifest_matches_python_manifest():
    path = REPO / "scripts" / "paderborn" / "zenodo_real3_manifest.csv"
    with path.open(newline="", encoding="ascii") as fh:
        rows = list(csv.DictReader(fh))
    assert {r["file"].removesuffix(".rar") for r in rows} == set(TASKS["real3"].bearings)
    for r in rows:
        spec = ZENODO_MANIFEST[r["file"].removesuffix(".rar")]
        assert (int(r["bytes"]), r["md5"]) == (spec.bytes, spec.md5)


def test_md5sum_matches_hashlib(tmp_path):
    data = bytes(range(256)) * 5000
    f = tmp_path / "x.bin"
    f.write_bytes(data)
    assert md5sum(f, block=4096) == hashlib.md5(data).hexdigest()


def _archive(folder: Path, code: str, content: bytes) -> ArchiveSpec:
    (folder / f"{code}.rar").write_bytes(content)
    return ArchiveSpec(f"{code}.rar", len(content), hashlib.md5(content).hexdigest())


def test_verify_archives_statuses(tmp_path):
    good = _archive(tmp_path, "K001", b"healthy bearing archive")
    bad_md5 = _archive(tmp_path, "KA04", b"outer race archive")
    (tmp_path / "KA04.rar").write_bytes(b"outer race archivX")  # same size, other bytes
    short = _archive(tmp_path, "KI04", b"inner race archive")
    (tmp_path / "KI04.rar").write_bytes(b"inner")
    manifest = {
        "K001": good,
        "KA04": bad_md5,
        "KI04": short,
        "K002": ArchiveSpec("K002.rar", 10, "0" * 32),
    }
    rows = verify_archives(
        tmp_path, bearings=["K001", "KA04", "KI04", "K002", "KA08"], manifest=manifest
    )
    status = {r["bearing"]: r["status"] for r in rows}
    assert status == {
        "K001": "ok",
        "KA04": "md5_mismatch",
        "KI04": "size_mismatch",
        "K002": "missing",
        "KA08": "not_in_manifest",
    }
    assert "md5" not in next(r for r in rows if r["bearing"] == "KI04")  # size checked first


def test_verify_archives_validation(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_archives(tmp_path / "nope")
    with pytest.raises(ValueError, match="unknown task"):
        verify_archives(tmp_path, task="nope")
    with pytest.raises(ValueError, match="unknown bearing"):
        verify_archives(tmp_path, bearings=["X999"])
    rows = verify_archives(tmp_path, task=None)
    assert len(rows) == len(BEARINGS)


def _full_bearing(root: Path, code: str, measurements: int = 20) -> None:
    for oc in OPERATING_CONDITIONS:
        for m in range(1, measurements + 1):
            p = root / code / f"{oc}_{code}_{m}.mat"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"")  # inventory only reads names


def test_inventory_complete_and_problems(tmp_path):
    _full_bearing(tmp_path, "K001")
    _full_bearing(tmp_path, "KA04")
    (tmp_path / "KA04" / "N09_M07_F10_KA04_7.mat").unlink()  # gap
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy" / "N15_M07_F10_KA04_3.mat").write_bytes(b"")  # duplicate
    (tmp_path / "KA04" / "N15_M01_F10_KA04_21.mat").write_bytes(b"")  # extra index
    inv = check_inventory(tmp_path, bearings=["K001", "KA04", "KI04"])
    assert inv["expected_per_bearing"] == 80
    assert inv["bearings"]["K001"]["complete"] is True
    assert inv["bearings"]["K001"]["n_files"] == 80
    ka04 = inv["bearings"]["KA04"]["conditions"]
    assert ka04["N09_M07_F10"]["missing_indices"] == [7]
    assert ka04["N15_M07_F10"]["duplicates"] == [3]
    assert ka04["N15_M01_F10"]["extra_indices"] == [21]
    assert inv["bearings"]["KI04"]["n_files"] == 0
    assert inv["complete"] is False


def test_verification_file_round_trip_and_feature_report(tmp_path):
    write_dataset(tmp_path, sorted(TASKS["real3"].bearings), measurements=1)
    inv = check_inventory(tmp_path)
    archives = [{"bearing": "K001", "file": "K001.rar", "status": "ok"}]
    path = write_verification(tmp_path, archives, inv)
    assert path.name == VERIFICATION_FILE
    stored = load_verification(tmp_path)
    assert stored["mirror"]["doi"] == "10.5281/zenodo.15845309"
    assert stored["mirror"]["missing_from_mirror"] == ["KA08"]
    assert stored["license_of_original_data"] == "CC BY-NC 4.0"
    assert stored["archives_ok"] is True
    assert stored["inventory_complete"] is False  # only 1 of 20 measurements per condition
    assert load_verification(tmp_path / "K001") is None

    from pumpguard.datasets.paderborn import build_feature_table

    _, report = build_feature_table(
        tmp_path,
        task="real3",
        expected_duration_s=FIXTURE_DURATION_S,
        segment_seconds=FIXTURE_DURATION_S / 2,
    )
    assert report["archive_verification"]["mirror"]["doi"] == "10.5281/zenodo.15845309"
    assert report["archive_verification"]["inventory_complete"] is False


def test_feature_report_says_when_unverified(tmp_path):
    write_dataset(tmp_path, ["K001", "KA04", "KI04"], measurements=1)
    from pumpguard.datasets.paderborn import build_feature_table

    _, report = build_feature_table(
        tmp_path,
        task="real3",
        expected_duration_s=FIXTURE_DURATION_S,
        segment_seconds=FIXTURE_DURATION_S / 2,
    )
    assert report["archive_verification"].startswith("not verified")


def test_cli_verify(tmp_path, capsys):
    data = tmp_path / "data"
    for code in TASKS["real3"].bearings:
        _full_bearing(data, code)
    assert main(["paderborn", "verify", str(data)]) == 0
    out = capsys.readouterr().out
    assert "All checks passed" in out
    assert json.loads((data / VERIFICATION_FILE).read_text(encoding="utf-8"))["inventory_complete"]

    arch = tmp_path / "archives"
    arch.mkdir()
    assert main(["paderborn", "verify", str(data), "--archives", str(arch)]) == 1
    out = capsys.readouterr().out
    assert "K001.rar   missing" in out
    assert "Problems found" in out

    (data / "KI21" / "N15_M07_F04_KI21_20.mat").unlink()
    assert main(["paderborn", "verify", str(data)]) == 1
    assert "KI21" in capsys.readouterr().out
