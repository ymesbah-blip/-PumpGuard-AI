"""Consistency of protocol amendment 2 (Markdown) with its config JSON and the v0.4 evidence."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts/protocol/check_amendment2.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_amendment2", CHECKER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


chk = _load_checker()


@pytest.fixture
def copies(tmp_path: Path) -> tuple[Path, Path]:
    md = tmp_path / chk.DEFAULT_MD.name
    cfg = tmp_path / chk.DEFAULT_CONFIG.name
    shutil.copy(chk.DEFAULT_MD, md)
    shutil.copy(chk.DEFAULT_CONFIG, cfg)
    return md, cfg


def _edit_config(path: Path, edit) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _failed(report) -> set[str]:  # type: ignore[no-untyped-def]
    return {c.name for c in report.failures}


def test_amendment_config_and_evidence_are_consistent() -> None:
    report = chk.run_checks()
    assert not report.failures, [(c.name, c.detail) for c in report.failures]
    assert len(report.checks) > 80


def test_band_sets_follow_the_frequency_rule_only() -> None:
    cfg = json.loads(chk.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    sets = chk.candidate_bands(cfg["bands"]["rule"], cfg["bands"]["default_D0"])
    assert [len(sets[k]) for k in ("grid_44", "excluded_9", "eligible_35", "full_45")] == [
        44,
        9,
        35,
        45,
    ]
    widths = [hi - lo for lo, hi in sets["grid_44"]]
    assert [widths.count(b) for b in (2000, 4000, 8000, 16000)] == [25, 12, 5, 2]
    excluded_khz = {(lo // 1000, hi // 1000) for lo, hi in sets["excluded_9"]}
    assert excluded_khz == {
        (14, 16),
        (15, 17),
        (16, 18),
        (13, 17),
        (15, 19),
        (9, 17),
        (13, 21),
        (1, 17),
        (9, 25),
    }
    assert all(lo >= 1000 and hi <= 27000 for lo, hi in sets["grid_44"])
    assert sets["full_45"][-1] == [6400, 25600]


def test_parameter_drift_between_markdown_and_config_is_detected(
    copies: tuple[Path, Path],
) -> None:
    md, cfg = copies
    _edit_config(cfg, lambda d: d["selection"].update(delta=0.04))
    failed = _failed(chk.run_checks(md, cfg))
    assert {"registered:selection.delta", "prose:12:delta", "prose:9.2:delta"} <= failed


def test_permutation_count_change_must_reach_every_section(copies: tuple[Path, Path]) -> None:
    md, cfg = copies

    def to_1000(d: dict) -> None:  # type: ignore[type-arg]
        s3 = d["statistics"]["S3_permutation"]
        s3["permutations"] = 1000
        s3["permutations_owner_decision"]["registered"] = 1000

    _edit_config(cfg, to_1000)
    failed = _failed(chk.run_checks(md, cfg))
    assert {
        "registered:statistics.S3_permutation.permutations",
        "prose:10.2:permutations",
        "prose:12:permutations",
    } <= failed


def test_status_fields_must_agree(copies: tuple[Path, Path]) -> None:
    md, cfg = copies
    current = json.loads(cfg.read_text(encoding="utf-8"))["protocol_status"]
    other = "DRAFT" if current == "FROZEN" else "FROZEN"
    _edit_config(cfg, lambda d: d.update(protocol_status=other))
    failed = _failed(chk.run_checks(md, cfg))
    assert {"status:header", "status:final-line"} <= failed


# The approved design (amendment 2, review 2, pre-freeze audit and owner decision D-perm).
# Changing any of these values needs a new amendment, not an edit.
APPROVED_DESIGN = {
    "task": "real3",
    "primary_condition": "N09_M07_F10",
    "channel": "vibration_1",
    "fs_hz": 64000,
    "segment_seconds": 1.0,
    "bearing_geometry": "6203",
    "envelope_filter.order": 4,
    "feature.names": ["env_bpfo_ratio", "env_bpfi_ratio"],
    "bands.rule.bandwidths_hz": [2000, 4000, 8000, 16000],
    "bands.rule.f_lo_min_hz": 1000,
    "bands.rule.f_hi_max_hz": 27000,
    "bands.rule.switching_frequency_hz": 16000,
    "bands.default_D0": [6400, 25600],
    "selection.delta": 0.05,
    "selection.tie_break": ["wider bandwidth", "lower f_lo"],
    "selection.inner_k": 4,
    "selection.inner_seed_base": 1000,
    "outer.k": 5,
    "outer.seed": 0,
    "arms": ["V1", "C0", "R0", "V1-45", "V2", "VG"],
    "statistics.S1_marginal_bootstrap.replicates": 1000,
    "statistics.S1_marginal_bootstrap.seed": 0,
    "statistics.S1_marginal_bootstrap.stratified": False,
    "statistics.S1_marginal_bootstrap.level": 0.95,
    "statistics.S2_paired_bootstrap.replicates": 10000,
    "statistics.S2_paired_bootstrap.seed": 0,
    "statistics.S2_paired_bootstrap.stratified_by_class": True,
    "statistics.S2_paired_bootstrap.per_class_draws": 5,
    "statistics.S3_permutation.permutations": 9999,
    "statistics.S3_permutation.seed": 12345,
    "statistics.S3_permutation.refolds": True,
    "statistics.S3_permutation.sequential_extension": False,
    "decision.P2_alpha": 0.05,
    "decision.H1_supported": "P1 and P3 and P2",
    "gates.G2.files_N09": 300,
    "gates.G2.segments_N09": 1196,
    "gates.G3.R0_detection_ba_N09_expected": 0.4685836297141851,
    "gates.G3.abs_tolerance": 1e-9,
    "gates.G4a.resonance_hz": 3000,
    "gates.G4a.min_folds": 4,
    "gates.G4a.min_delta_ba": 0.2,
    "gates.G4a.require_S2_lower_bound_gt_0": True,
    "gates.G4b.resonance_hz": 8000,
    "gates.G4b.min_folds": 4,
    "gates.G4b.min_delta_ba": -0.05,
    "gates.G5.datasets": 20,
    "gates.G5.permutations_each": 200,
    "gates.G5.alpha": 0.05,
    "gates.G5.max_significant": 3,
    "synthetic.data_seed": 2026,
    "synthetic.machines_per_class": 5,
    "synthetic.segments_per_machine": 20,
    "synthetic.rpm": 900,
    "synthetic.fs_hz": 64000,
}


def test_config_matches_the_approved_design() -> None:
    cfg = json.loads(chk.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    changed = {
        path: (expected, chk.resolve(cfg, path))
        for path, expected in APPROVED_DESIGN.items()
        if not chk.same_value(expected, chk.resolve(cfg, path))
    }
    assert not changed, changed
    folds = cfg["gates"]["G3"]["outer_folds_v04"]
    assert folds == {
        "0": ["K003", "KA04", "KI21"],
        "1": ["K005", "KA16", "KI14"],
        "2": ["K004", "KA22", "KI16"],
        "3": ["K001", "KA30", "KI04"],
        "4": ["K002", "KA15", "KI18"],
    }


def test_edit_to_a_frozen_file_is_detected(copies: tuple[Path, Path]) -> None:
    md, cfg = copies
    if json.loads(cfg.read_text(encoding="utf-8"))["protocol_status"] != "FROZEN":
        pytest.skip("the amendment is not frozen yet")
    assert not chk.run_checks(md, cfg).failures
    md.write_bytes(md.read_bytes().replace(b"seed 12345", b"seed 12346", 1))
    assert "freeze:amendment-sha256" in _failed(chk.run_checks(md, cfg))


def test_wording_removed_by_the_audit_cannot_return(copies: tuple[Path, Path]) -> None:
    md, cfg = copies
    text = md.read_text(encoding="utf-8")
    heading = "### 2.1 Identity of the v0.4 evidence"
    md.write_text(text.replace(heading, heading + "\n\nplus three changes"), encoding="utf-8")
    assert "stale:plus three changes" in _failed(chk.run_checks(md, cfg))


def test_changed_evidence_file_is_detected(copies: tuple[Path, Path], tmp_path: Path) -> None:
    md, cfg = copies
    evidence = tmp_path / "evidence"
    shutil.copytree(chk.DEFAULT_EVIDENCE, evidence)
    target = evidence / "leakage_results.json"
    target.write_bytes(target.read_bytes() + b"\n")
    failed = _failed(chk.run_checks(md, cfg, evidence))
    assert failed == {"evidence:leakage_results.json:sha256"}


def test_json_report_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    assert chk.main(["--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["failed"] == 0
    assert {"name", "ok", "detail"} <= set(report["checks"][0])
