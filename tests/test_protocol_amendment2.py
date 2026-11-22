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

    def to_9999(d: dict) -> None:  # type: ignore[type-arg]
        s3 = d["statistics"]["S3_permutation"]
        s3["permutations"] = 9999
        s3["permutations_owner_decision"]["registered"] = 9999

    _edit_config(cfg, to_9999)
    failed = _failed(chk.run_checks(md, cfg))
    assert {
        "registered:statistics.S3_permutation.permutations",
        "prose:10.2:permutations",
        "prose:12:permutations",
    } <= failed


def test_status_fields_must_agree(copies: tuple[Path, Path]) -> None:
    md, cfg = copies
    _edit_config(cfg, lambda d: d.update(protocol_status="FROZEN"))
    failed = _failed(chk.run_checks(md, cfg))
    assert {
        "status:header",
        "status:final-line",
        "status:frozen-has-decision",
        "status:frozen-has-signoff-date",
    } <= failed


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
