"""Consistency checker for protocol amendment 2 (v0.5 demodulation-band selection).

Compares the Markdown amendment with its machine-readable config and with the published v0.4
evidence. It reads files only and changes nothing.

Checks:

* every row of the "Registered parameters" table (section 18) equals the config value;
* the 44 / 9 / 35 / 45 band sets recomputed from the rule equal the config lists, and the prose
  of section 8.1 names the same excluded bands and per-bandwidth counts;
* the prose of sections 9.2, 10.2, 12 and 13 states the same delta, permutation count and G3
  value as the config;
* the header status, the final status line and the config ``protocol_status`` agree, and a
  FROZEN protocol has an owner decision and a sign-off date;
* the four evidence hashes in the config appear in section 2.1 and match the files;
* the G3 expected value equals the stored v0.4 value, and the G3 fold list equals the folds
  recomputed with ``pumpguard.evaluation.stratified_group_kfold`` (skipped if the package is
  not importable);
* wording removed after the pre-freeze audit does not come back;
* once the amendment is FROZEN: the SHA-256 values in the freeze record and in ``CHANGELOG.md``
  equal the hashes of the two files, so any later edit to a frozen file is reported.

Usage::

    python scripts/protocol/check_amendment2.py            # human-readable, exit 1 on failure
    python scripts/protocol/check_amendment2.py --json     # machine-readable report
    python scripts/protocol/check_amendment2.py --no-freeze-record   # freeze step 3 only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MD = REPO / "docs/protocol/amendment-v0.5-demodulation-band-selection.md"
DEFAULT_CONFIG = REPO / "docs/protocol/amendment-v0.5-config.json"
DEFAULT_EVIDENCE = REPO / "docs/results/paderborn-real3"
DEFAULT_FREEZE = REPO / "docs/protocol/amendment-v0.5-freeze-record.json"
DEFAULT_CHANGELOG = REPO / "CHANGELOG.md"

TABLE_START = "<!-- registered-parameters:start -->"
TABLE_END = "<!-- registered-parameters:end -->"
DRAFT_FOOTER = "**PROTOCOL STATUS: DRAFTED — NOT YET EXPERIMENTALLY EXECUTED.**"
FROZEN_FOOTER_PREFIX = "**PROTOCOL STATUS: FROZEN"

# Wording that the pre-freeze audit found wrong. It must not reappear.
STALE_PHRASES = {
    "plus three changes": "A1: the report-header fix came after the run",
    "anti-alias filter is 2nd order": "A2: the 30 kHz filter is a signal-conditioning low-pass",
    "= 16 in every used file": "A7: the sample ratio is about 16, not exactly 16",
    "must reproduce 0.469 (gate G3)": "A3: G3 uses the exact stored value",
    "equals the v0.4 value 0.469": "A3: G3 uses the exact stored value",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": not self.failures,
            "passed": len(self.checks) - len(self.failures),
            "failed": len(self.failures),
            "skipped": self.skipped,
            "checks": [asdict(c) for c in self.checks],
        }


# ---------------------------------------------------------------------------- helpers


def candidate_bands(rule: dict[str, Any], default_d0: list[int]) -> dict[str, list[list[int]]]:
    """Band sets from the frequency rule alone (no data argument)."""
    f_lo_min, f_hi_max = int(rule["f_lo_min_hz"]), int(rule["f_hi_max_hz"])
    switching = int(rule["switching_frequency_hz"])
    grid: list[list[int]] = []
    for bandwidth in rule["bandwidths_hz"]:
        step, f_lo = int(bandwidth) // 2, f_lo_min
        while f_lo + int(bandwidth) <= f_hi_max:
            grid.append([f_lo, f_lo + int(bandwidth)])
            f_lo += step
    excluded = [b for b in grid if b[0] <= switching <= b[1]]
    eligible = [b for b in grid if not b[0] <= switching <= b[1]]
    return {
        "grid_44": grid,
        "excluded_9": excluded,
        "eligible_35": eligible,
        "full_45": [*grid, list(default_d0)],
    }


def resolve(config: dict[str, Any], path: str) -> Any:
    """Value at a dotted path; ``len(a.b)`` returns the length of the list at ``a.b``."""
    match = re.fullmatch(r"len\((.+)\)", path)
    target: Any = config
    for key in (match.group(1) if match else path).split("."):
        if not isinstance(target, dict) or key not in target:
            raise KeyError(path)
        target = target[key]
    return len(target) if match else target


def same_value(a: Any, b: Any) -> bool:
    """Equality that does not treat True as 1 or a string as a number."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def grouped(n: int) -> str:
    """Number as written in the amendment: 1 000, 10 000, 9 999."""
    return f"{n:,}".replace(",", " ")


def section(markdown: str, heading: str) -> str:
    """Text from a heading line that starts with ``heading`` up to the next heading."""
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#") and line.lstrip("#").strip().startswith(heading):
            level = len(line) - len(line.lstrip("#"))
            body = []
            for nxt in lines[i + 1 :]:
                if nxt.startswith("#") and len(nxt) - len(nxt.lstrip("#")) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


def registered_rows(markdown: str) -> list[tuple[str, str, str]]:
    if TABLE_START not in markdown or TABLE_END not in markdown:
        return []
    block = markdown.split(TABLE_START, 1)[1].split(TABLE_END, 1)[0]
    rows = []
    for line in block.strip().splitlines()[2:]:  # skip header and separator
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3:
            rows.append((cells[0], cells[1].strip("`"), cells[2].strip("`")))
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------- checks


def check_registered(report: Report, md: str, cfg: dict[str, Any]) -> None:
    rows = registered_rows(md)
    report.add("registered-table-present", bool(rows), f"{len(rows)} rows")
    for label, raw, path in rows:
        name = f"registered:{path}"
        try:
            expected = json.loads(raw)
        except json.JSONDecodeError:
            report.add(name, False, f"value for {label!r} is not JSON: {raw}")
            continue
        try:
            actual = resolve(cfg, path)
        except KeyError:
            report.add(name, False, f"config has no path {path}")
            continue
        ok = same_value(expected, actual)
        report.add(name, ok, "" if ok else f"Markdown {expected!r} != config {actual!r}")


def check_bands(report: Report, md: str, cfg: dict[str, Any]) -> None:
    bands = cfg["bands"]
    computed = candidate_bands(bands["rule"], bands["default_D0"])
    for key, value in computed.items():
        ok = bands.get(key) == value
        report.add(f"bands:{key}", ok, "" if ok else "config list differs from the rule")
        expected_len = int(key.rsplit("_", 1)[1])
        report.add(f"bands:{key}:count", len(value) == expected_len, f"{len(value)} bands")

    text = section(md, "8.1")
    widths = [b[1] - b[0] for b in computed["grid_44"]]
    per_bw = {bw: widths.count(bw) for bw in (2000, 4000, 8000, 16000)}
    phrase = (
        f"{per_bw[2000]} at 2 kHz, {per_bw[4000]} at 4 kHz, "
        f"{per_bw[8000]} at 8 kHz, {per_bw[16000]} at 16 kHz"
    )
    report.add("prose:8.1:per-bandwidth-counts", phrase in text, phrase)
    named = re.findall(r"\((\d+), (\d+)\)", text.split("Switching exclusion", 1)[-1])
    named_hz = sorted([int(a) * 1000, int(b) * 1000] for a, b in named)
    ok = named_hz == sorted(computed["excluded_9"])
    report.add("prose:8.1:excluded-bands", ok, f"{len(named_hz)} named in the text")


def check_prose(report: Report, md: str, cfg: dict[str, Any]) -> None:
    n_perm = int(cfg["statistics"]["S3_permutation"]["permutations"])
    s3_seed = cfg["statistics"]["S3_permutation"]["seed"]
    stats = section(md, "10.2")
    report.add(
        "prose:10.2:permutations",
        f"Do this for {grouped(n_perm)} permutations" in stats
        and f"N = {grouped(n_perm)}" in stats
        and f"p = (1 + k) / {grouped(n_perm + 1)}" in stats,
        f"expects {grouped(n_perm)} permutations and denominator {grouped(n_perm + 1)}",
    )
    repro = section(md, "12.")
    report.add(
        "prose:12:permutations",
        f"S3 permutation seed {s3_seed}, {grouped(n_perm)} permutations" in repro,
        f"expects seed {s3_seed} and {grouped(n_perm)} permutations",
    )
    delta = cfg["selection"]["delta"]
    report.add("prose:12:delta", f"δ = {delta}" in repro, f"δ = {delta}")
    report.add(
        "prose:9.2:delta",
        f"S[D0] + {delta}" in section(md, "9.2"),
        f"pseudo-code margin {delta}",
    )
    g3 = cfg["gates"]["G3"]
    gates = section(md, "13.")
    g3_row = next((ln for ln in gates.splitlines() if ln.startswith("| G3 |")), "")
    tol = f"{g3['abs_tolerance']:.0e}".replace("e-0", "e-")
    ok = repr(g3["R0_detection_ba_N09_expected"]) in g3_row and tol in g3_row
    report.add("prose:13:G3-value", ok, f"expects {g3['R0_detection_ba_N09_expected']!r} and {tol}")
    folds_ok = all(
        f"fold {k} = {{{', '.join(v)}}}" in g3_row for k, v in g3["outer_folds_v04"].items()
    )
    report.add("prose:13:G3-folds", folds_ok, "fold list in the G3 row")


def check_status(report: Report, md: str, cfg: dict[str, Any]) -> None:
    status = cfg.get("protocol_status")
    report.add("status:config-value", status in {"DRAFT", "FROZEN"}, f"protocol_status={status!r}")
    header = next((ln for ln in md.splitlines() if ln.startswith("| Status |")), "")
    report.add("status:header", f"**{status}**" in header, header[:80])
    last = md.rstrip().splitlines()[-1] if md.strip() else ""
    if status == "FROZEN":
        footer_ok = last.startswith(FROZEN_FOOTER_PREFIX)
    else:
        footer_ok = last == DRAFT_FOOTER
    report.add("status:final-line", footer_ok, last[:80])
    decision = cfg["statistics"]["S3_permutation"].get("permutations_owner_decision", {})
    registered = decision.get("registered")
    report.add(
        "status:permutation-decision-registered",
        registered == cfg["statistics"]["S3_permutation"]["permutations"],
        f"registered={registered!r}",
    )
    if status == "FROZEN":
        frozen_on = str(cfg.get("frozen_on", ""))
        report.add(
            "status:frozen-date",
            bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", frozen_on))
            and frozen_on in header
            and frozen_on in last,
            f"frozen_on={frozen_on!r} must appear in the header and the final line",
        )
        report.add(
            "status:frozen-has-decision",
            decision.get("status") not in {None, "PENDING"},
            f"decision status {decision.get('status')!r}",
        )
        signoff = next(
            (ln for ln in md.splitlines() if ln.startswith("| Project owner, final sign-off")), ""
        )
        cells = [c.strip() for c in signoff.strip().strip("|").split("|")]
        report.add(
            "status:frozen-has-signoff-date",
            len(cells) == 4 and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[3])),
            signoff[:80],
        )


def check_evidence(report: Report, md: str, cfg: dict[str, Any], evidence: Path | None) -> None:
    hashes: dict[str, str] = cfg["evidence_sha256"]
    identity = section(md, "2.1")
    for name, digest in hashes.items():
        report.add(f"evidence:{name}:in-2.1", digest in identity, digest[:12])
    if evidence is None:
        report.skipped.append("evidence files (--no-evidence-files)")
        return
    for name, digest in hashes.items():
        path = evidence / name
        if not path.is_file():
            report.add(f"evidence:{name}:file", False, f"missing {path}")
            continue
        actual = sha256(path)
        report.add(f"evidence:{name}:sha256", actual == digest, actual[:12])

    bench = evidence / "benchmark_results.json"
    if not bench.is_file():
        return
    results = json.loads(bench.read_text(encoding="utf-8"))["results"]
    rule = next(
        (r for r in results["tasks"]["detection"] if r.get("baseline") == "envelope_rule"), None
    )
    stored = None if rule is None else rule["per_condition"].get(cfg["primary_condition"])
    expected = cfg["gates"]["G3"]["R0_detection_ba_N09_expected"]
    report.add("evidence:G3-value", stored == expected, f"stored {stored!r}")

    try:
        sys.path.insert(0, str(REPO / "src"))
        from pumpguard.evaluation import stratified_group_kfold
    except ImportError:
        report.skipped.append("G3 fold recomputation (pumpguard not importable)")
        return
    per_group = results["tasks"]["diagnosis"][0]["per_group"]
    groups = [g["group"] for g in per_group]
    labels = [g["label"] for g in per_group]
    outer = cfg["outer"]
    folds = stratified_group_kfold(groups, labels, n_splits=outer["k"], seed=outer["seed"])
    recomputed = {str(k): sorted(groups[i] for i in test) for k, (_, test) in enumerate(folds)}
    registered = {k: sorted(v) for k, v in cfg["gates"]["G3"]["outer_folds_v04"].items()}
    report.add("evidence:G3-folds", recomputed == registered, json.dumps(recomputed))


def check_freeze(
    report: Report,
    markdown_path: Path,
    config_path: Path,
    cfg: dict[str, Any],
    freeze_record: Path | None,
    changelog: Path,
) -> None:
    if freeze_record is None:
        report.skipped.append("freeze record (--no-freeze-record)")
        return
    if cfg.get("protocol_status") != "FROZEN":
        report.add(
            "freeze:no-record-while-draft",
            not freeze_record.is_file(),
            f"{freeze_record.name} must not exist before the freeze",
        )
        return
    if not freeze_record.is_file():
        report.add("freeze:record-present", False, f"missing {freeze_record}")
        return
    record = json.loads(freeze_record.read_text(encoding="utf-8"))
    md_hash, cfg_hash = sha256(markdown_path), sha256(config_path)
    report.add(
        "freeze:amendment-sha256",
        record.get("amendment", {}).get("sha256") == md_hash,
        f"file {md_hash[:12]}",
    )
    report.add(
        "freeze:config-sha256",
        record.get("config", {}).get("sha256") == cfg_hash,
        f"file {cfg_hash[:12]}",
    )
    report.add(
        "freeze:paths",
        record.get("amendment", {}).get("path") == cfg["amendment"]
        and record.get("config", {}).get("path") == f"docs/protocol/{config_path.name}",
        "record names the amendment and the config",
    )
    report.add(
        "freeze:status-and-date",
        record.get("protocol_status") == "FROZEN" and record.get("frozen_on") == cfg["frozen_on"],
        f"record {record.get('protocol_status')!r} {record.get('frozen_on')!r}",
    )
    report.add(
        "freeze:permutations",
        record.get("permutations") == cfg["statistics"]["S3_permutation"]["permutations"],
        f"record {record.get('permutations')!r}",
    )
    report.add(
        "freeze:evidence",
        record.get("evidence_sha256") == cfg["evidence_sha256"]
        and record.get("evidence_commit") == cfg["evidence_commit"],
        "record repeats the evidence hashes and commit",
    )
    text = changelog.read_text(encoding="utf-8") if changelog.is_file() else ""
    report.add(
        "freeze:changelog",
        md_hash in text and cfg_hash in text,
        f"{changelog.name} lists both hashes",
    )


def check_stale(report: Report, md: str) -> None:
    # The revision history (section 17) quotes the old wording on purpose.
    body = md.replace(section(md, "17."), "")
    for phrase, reason in STALE_PHRASES.items():
        report.add(f"stale:{phrase}", phrase not in body, reason)


def check_links(report: Report, md: str, cfg: dict[str, Any], config_path: Path) -> None:
    report.add(
        "link:markdown-names-config",
        f"]({config_path.name})" in md,
        f"header links {config_path.name}",
    )
    report.add(
        "link:config-names-markdown",
        (REPO / cfg["amendment"]).is_file(),
        cfg["amendment"],
    )


def run_checks(
    markdown_path: Path = DEFAULT_MD,
    config_path: Path = DEFAULT_CONFIG,
    evidence_dir: Path | None = DEFAULT_EVIDENCE,
    freeze_record: Path | None = DEFAULT_FREEZE,
    changelog: Path = DEFAULT_CHANGELOG,
) -> Report:
    md = markdown_path.read_text(encoding="utf-8")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    report = Report()
    check_registered(report, md, cfg)
    check_bands(report, md, cfg)
    check_prose(report, md, cfg)
    check_status(report, md, cfg)
    check_evidence(report, md, cfg, evidence_dir)
    check_stale(report, md)
    check_links(report, md, cfg, config_path)
    check_freeze(report, markdown_path, config_path, cfg, freeze_record, changelog)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument(
        "--no-evidence-files", action="store_true", help="skip hashing the evidence files"
    )
    parser.add_argument("--freeze-record", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    parser.add_argument(
        "--no-freeze-record",
        action="store_true",
        help="skip the freeze-record checks (freeze step 3, before the hashes exist)",
    )
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)
    evidence = None if args.no_evidence_files else args.evidence
    freeze = None if args.no_freeze_record else args.freeze_record
    report = run_checks(args.markdown, args.config, evidence, freeze, args.changelog)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    else:
        for check in report.failures:
            print(f"FAIL {check.name}: {check.detail}")
        for item in report.skipped:
            print(f"SKIP {item}")
        summary = report.as_dict()
        print(f"{summary['passed']} passed, {summary['failed']} failed")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
