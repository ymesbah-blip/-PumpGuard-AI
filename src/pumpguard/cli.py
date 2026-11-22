"""Command-line interface: ``pumpguard <command> [options]``.

Commands:
    demo       generate one synthetic signal, print features, save CSV/JSON/PNG
    features   compute features for any signal CSV (time_s, vibration)
    dataset    build a labelled synthetic feature table
    bearing    print bearing defect frequencies for a shaft speed
    paderborn  index / inspect / extract features from local Paderborn KAt files
    benchmark  leakage-safe benchmark of transparent baselines (+ learned models with --learned)
    leakage    the same model under a random split vs a group split
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from ._version import __version__
from .bearings import BEARING_PRESETS, BearingGeometry
from .signals import CONDITION_ALIASES, CONDITIONS

__all__ = ["build_parser", "main"]


def _print_features(features: dict[str, float]) -> None:
    width = max(len(k) for k in features) + 2
    for key, value in features.items():
        shown = "n/a" if math.isnan(value) else f"{value:.4f}"
        print(f"  {key:<{width}}{shown:>12}")


def _bearing_from_args(args: argparse.Namespace) -> BearingGeometry | None:
    if getattr(args, "ball_mm", None) is not None:
        return BearingGeometry(
            n_elements=args.n_elements,
            ball_diameter_mm=args.ball_mm,
            pitch_diameter_mm=args.pitch_mm,
            contact_angle_deg=args.angle,
        )
    preset = getattr(args, "bearing", None)
    return BearingGeometry.from_preset(preset) if preset else None


# ------------------------------------------------------------------ commands


def _cmd_demo(args: argparse.Namespace) -> int:
    from .features import extract_all_features
    from .health import demo_health_score
    from .io import save_signal
    from .signals import SignalConfig, simulate

    condition = args.condition
    if condition in CONDITION_ALIASES:
        print(
            f"note: {condition!r} is deprecated, using {CONDITION_ALIASES[condition]!r}",
            file=sys.stderr,
        )
        condition = CONDITION_ALIASES[condition]

    cfg = SignalConfig(
        condition=condition,
        fs=args.fs,
        duration=args.duration,
        rpm=args.rpm,
        seed=args.seed,
        severity=args.severity,
        noise_std=args.noise,
        n_vanes=args.n_vanes,
    )
    sig = simulate(cfg)
    feats = extract_all_features(
        sig.x, sig.fs, rpm=cfg.rpm, n_vanes=cfg.n_vanes, bearing=cfg.bearing
    )

    out = Path(args.out)
    stem = f"{condition}_signal"
    csv_path, json_path = save_signal(out / f"{stem}.csv", sig.t, sig.x, sig.metadata())

    print(f"Condition: {condition}  (SYNTHETIC demo data - not a measurement)")
    print(f"fs={cfg.fs:g} Hz  duration={cfg.duration:g} s  rpm={cfg.rpm:g}  seed={cfg.seed}")
    _print_features(feats)
    print(f"Toy health score (RMS only, not calibrated): {demo_health_score(feats)}/100")
    print(f"Saved CSV:      {csv_path}")
    print(f"Saved metadata: {json_path}")
    if not args.no_plot:
        from .plotting import plot_signal_overview

        png = plot_signal_overview(
            sig.t,
            sig.x,
            sig.fs,
            out / f"{stem}.png",
            title=f"Synthetic vibration: {condition} (rpm={cfg.rpm:g}, synthetic data)",
            rpm=cfg.rpm,
            n_vanes=cfg.n_vanes,
            bearing=cfg.bearing,
        )
        print(f"Saved plot:     {png}")
    return 0


def _cmd_features(args: argparse.Namespace) -> int:
    from .features import extract_all_features
    from .io import load_signal

    loaded = load_signal(args.csv, fs=args.fs)
    meta_cfg = loaded.metadata.get("config", {})
    rpm = args.rpm if args.rpm is not None else meta_cfg.get("rpm")
    n_vanes = args.n_vanes if args.n_vanes is not None else meta_cfg.get("n_vanes")
    bearing = _bearing_from_args(args)
    if bearing is None and "bearing" in meta_cfg:
        bearing = BearingGeometry(**meta_cfg["bearing"])

    feats = extract_all_features(loaded.x, loaded.fs, rpm=rpm, n_vanes=n_vanes, bearing=bearing)
    if args.json:
        record = {
            "source": str(args.csv),
            "fs": loaded.fs,
            "rpm": rpm,
            "synthetic": loaded.metadata.get("synthetic"),
            "features": {k: (None if math.isnan(v) else v) for k, v in feats.items()},
        }
        print(json.dumps(record, indent=2))
        return 0

    print(f"Source: {args.csv}  (fs={loaded.fs:g} Hz, n={loaded.x.size})")
    if loaded.metadata.get("synthetic"):
        print("Metadata marks this signal as SYNTHETIC.")
    if rpm is None:
        print("No --rpm given: shaft-order and bearing features skipped.")
    _print_features(feats)
    return 0


def _cmd_dataset(args: argparse.Namespace) -> int:
    from .dataset import make_synthetic_dataset

    df = make_synthetic_dataset(
        conditions=args.conditions,
        machines_per_condition=args.machines,
        segments_per_machine=args.segments,
        duration=args.duration,
        seed=args.seed,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(
        f"Saved {len(df)} synthetic segments from {df['group_id'].nunique()} virtual machines "
        f"to {out}"
    )
    print("Split by 'group_id' (see pumpguard.dataset.group_train_test_split) to avoid leakage.")
    return 0


def _cmd_bearing(args: argparse.Namespace) -> int:
    bearing = _bearing_from_args(args)
    assert bearing is not None  # parser default guarantees a preset
    freqs = bearing.defect_frequencies(args.rpm)
    print(f"{bearing.name} at {args.rpm:g} rpm (kinematic, no slip):")
    labels = {
        "shaft_hz": "Shaft (1x)",
        "ftf": "FTF (cage)",
        "bpfo": "BPFO (outer race)",
        "bpfi": "BPFI (inner race)",
        "bsf": "BSF (ball spin)",
    }
    for key, value in freqs.as_dict().items():
        print(f"  {labels[key]:<20}{value:10.2f} Hz   ({value / freqs.shaft_hz:.4f} x shaft)")
    return 0


_PADERBORN_NOTICE = (
    "Paderborn KAt data: CC BY-NC 4.0 (non-commercial, attribution required). "
    "Bearing test rig, not a centrifugal pump."
)


def _cmd_paderborn_index(args: argparse.Namespace) -> int:
    from .datasets.paderborn import TASKS, scan

    index, skipped = scan(args.root)
    print(_PADERBORN_NOTICE)
    print(f"Recognised files: {len(index)}   unrecognised .mat files: {len(skipped)}")
    if len(index):
        table = index.pivot_table(
            index="bearing", columns="operating_condition", values="path", aggfunc="count"
        ).fillna(0)
        print(table.astype(int).to_string())
    for name, spec in TASKS.items():
        missing = sorted(spec.bearings - set(index["bearing"]))
        status = "complete" if not missing else f"missing {len(missing)}: {', '.join(missing)}"
        print(f"task {name:<20} {status}")
    for item in skipped[:10]:
        print(f"skipped {item['file']}: {item['reason']}", file=sys.stderr)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        index.drop(columns=["path"]).to_csv(out, index=False)
        print(f"Saved index: {out}")
    return 0


def _cmd_paderborn_verify(args: argparse.Namespace) -> int:
    from .datasets.paderborn_archives import check_inventory, verify_archives, write_verification

    print(_PADERBORN_NOTICE)
    archives = None
    if args.archives is not None:
        archives = verify_archives(args.archives, task=args.task)
        print(f"Archives in {args.archives} (sizes and MD5 from Zenodo {args.source} manifest):")
        for a in archives:
            print(f"  {a['file']:<10} {a['status']}")
    inventory = check_inventory(args.root, task=args.task)
    print(f"Extracted files under {args.root} (expected {inventory['expected_per_bearing']} each):")
    for code, b in inventory["bearings"].items():
        gaps = {
            oc: c for oc, c in b["conditions"].items()
            if c["missing_indices"] or c["extra_indices"] or c["duplicates"]
        }  # fmt: skip
        detail = "" if not gaps else "  problems: " + json.dumps(gaps)
        status = "ok" if b["complete"] else "INCOMPLETE"
        print(f"  {code:<6} {b['n_files']:>3} files  {status}{detail}")
    path = write_verification(args.root, archives, inventory, source=args.source)
    ok = inventory["complete"] and (archives is None or all(a["status"] == "ok" for a in archives))
    print(f"{'All checks passed' if ok else 'Problems found'}. Saved {path}")
    return 0 if ok else 1


def _cmd_paderborn_inspect(args: argparse.Namespace) -> int:
    from .datasets.paderborn import inspect_file

    rows = inspect_file(args.file)
    print(f"{args.file}:")
    print(f"  {'channel':<24}{'unit':<12}{'raster':<16}{'samples':>10}  documented fs")
    for r in rows:
        fs = "n/a" if r["documented_fs_hz"] is None else f"{r['documented_fs_hz']:g} Hz"
        print(f"  {r['name']:<24}{r['unit']:<12}{r['raster']:<16}{r['n_samples']:>10}  {fs}")
    return 0


def _cmd_paderborn_features(args: argparse.Namespace) -> int:
    from .datasets.paderborn import build_feature_table

    def progress(i: int, total: int, name: str) -> None:
        if i == 1 or i == total or i % 25 == 0:
            print(f"  [{i}/{total}] {name}", file=sys.stderr)

    print(_PADERBORN_NOTICE)
    df, report = build_feature_table(
        args.root,
        task=args.task,
        segment_seconds=args.segment_seconds,
        conditions=args.conditions,
        max_measurements=args.max_measurements,
        envelope_band=tuple(args.envelope_band) if args.envelope_band else None,
        expected_duration_s=args.expected_duration or None,
        progress=progress,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    sidecar = out.with_suffix(".json")
    sidecar.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        f"Saved {len(df)} segments from {report['n_files_used']} files "
        f"({len(report['failures'])} failed) to {out}"
    )
    print(f"Saved provenance report: {sidecar}")
    for failure in report["failures"][:10]:
        print(f"  failed {failure['file']}: {failure['error']}", file=sys.stderr)
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    import pandas as pd

    from .benchmark import run_benchmark, synthetic_feature_table, write_report

    dataset: dict[str, object] | None
    if args.synthetic:
        df = synthetic_feature_table(seed=args.seed)
        dataset = {"dataset_id": "synthetic", "task": "dry-run", "synthetic": True}
    elif args.features is None:
        raise ValueError("give a feature table CSV or --synthetic")
    else:
        df = pd.read_csv(args.features)
        sidecar = Path(args.features).with_suffix(".json")
        dataset = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else None
    results = run_benchmark(
        df, n_splits=args.n_splits, n_boot=args.n_boot, seed=args.seed, learned=args.learned
    )
    json_path, md_path = write_report(results, args.out, dataset)
    for task, rows in results["tasks"].items():
        for r in rows:
            lo, hi = r["ci95"]["balanced_accuracy"]
            print(
                f"{task:<10} {r['baseline']:<26} balanced accuracy "
                f"{r['metrics']['balanced_accuracy']:.3f}  [95% CI {lo:.2f}, {hi:.2f}]"
            )
    for task, models in results.get("decision", {}).items():
        for name, d in models.items():
            verdict = "beats all baselines" if d["beats_all_baselines"] else "does not beat all"
            print(f"decision   {task}/{name}: {verdict} (protocol rule)")
    print(f"Saved report:  {md_path}\nSaved results: {json_path}")
    return 0


def _cmd_leakage(args: argparse.Namespace) -> int:
    import pandas as pd

    from .benchmark import synthetic_feature_table
    from .leakage import compare_splits, write_leakage_report

    dataset: dict[str, object] | None
    if args.synthetic:
        low, high = args.severity
        df = synthetic_feature_table(
            seed=args.seed,
            machines=args.machines,
            segments=args.segments,
            severity_range=(low, high),
        )
        dataset = {
            "dataset_id": "synthetic",
            "synthetic": True,
            "settings": f"severity {low:g}-{high:g}, {args.machines} machines per class, "
            f"{args.segments} segments per machine",
        }
    elif args.features is None:
        raise ValueError("give a feature table CSV or --synthetic")
    else:
        df = pd.read_csv(args.features)
        sidecar = Path(args.features).with_suffix(".json")
        dataset = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else None
    results = compare_splits(
        df,
        label_col=args.label_col,
        group_col=args.group_col,
        models=args.models,
        n_repeats=args.repeats,
        n_splits=args.n_splits,
        seed=args.seed,
    )
    json_path, md_path = write_leakage_report(results, args.out, dataset)
    for name, m in results["models"].items():
        s = m["summary"]
        print(
            f"{name:<20} group k-fold {s['group_mean']:.3f}  random k-fold {s['random_mean']:.3f}"
            f"  inflation {s['inflation_mean']:+.3f}"
        )
    for name, reason in results["skipped_models"].items():
        print(f"{name:<20} skipped: {reason}")
    print(f"Saved report:  {md_path}\nSaved results: {json_path}")
    return 0


# -------------------------------------------------------------------- parser


def _add_bearing_args(p: argparse.ArgumentParser, default_preset: str | None) -> None:
    p.add_argument(
        "--bearing",
        choices=sorted(BEARING_PRESETS),
        default=default_preset,
        help="bearing geometry preset",
    )
    p.add_argument("--n-elements", type=int, help="custom bearing: number of rolling elements")
    p.add_argument("--ball-mm", type=float, help="custom bearing: ball diameter")
    p.add_argument("--pitch-mm", type=float, help="custom bearing: pitch diameter")
    p.add_argument("--angle", type=float, default=0.0, help="custom bearing: contact angle (deg)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pumpguard",
        description="PumpGuard AI - educational vibration-monitoring toolkit (synthetic data).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="generate a synthetic signal and analyse it")
    demo.add_argument("--condition", choices=[*CONDITIONS, *CONDITION_ALIASES], default="healthy")
    demo.add_argument("--rpm", type=float, default=1800.0)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--severity", type=float, default=1.0, help="fault amplitude multiplier")
    demo.add_argument("--noise", type=float, default=0.05, help="noise standard deviation")
    demo.add_argument("--fs", type=float, default=12_000.0, help="sampling rate (Hz)")
    demo.add_argument("--duration", type=float, default=2.0, help="seconds")
    demo.add_argument("--n-vanes", type=int, default=5, help="impeller vane count")
    demo.add_argument("--out", default="outputs", help="output directory")
    demo.add_argument("--no-plot", action="store_true", help="skip the PNG figure")
    demo.set_defaults(func=_cmd_demo)

    feats = sub.add_parser("features", help="compute features for a signal CSV")
    feats.add_argument("csv", type=Path, help="CSV with columns time_s, vibration")
    feats.add_argument("--fs", type=float, help="sampling rate; default: sidecar or time_s")
    feats.add_argument("--rpm", type=float, help="shaft speed; enables order/bearing features")
    feats.add_argument("--n-vanes", type=int, help="impeller vane count")
    _add_bearing_args(feats, default_preset=None)
    feats.add_argument("--json", action="store_true", help="print JSON instead of a table")
    feats.set_defaults(func=_cmd_features)

    ds = sub.add_parser("dataset", help="build a labelled synthetic feature table")
    ds.add_argument("--out", default="outputs/synthetic_features.csv")
    ds.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    ds.add_argument("--machines", type=int, default=4, help="virtual machines per condition")
    ds.add_argument("--segments", type=int, default=5, help="segments per machine")
    ds.add_argument("--duration", type=float, default=1.0, help="seconds per segment")
    ds.add_argument("--seed", type=int, default=0)
    ds.set_defaults(func=_cmd_dataset)

    br = sub.add_parser("bearing", help="bearing defect frequencies")
    br.add_argument("--rpm", type=float, required=True)
    _add_bearing_args(br, default_preset="6205")
    br.set_defaults(func=_cmd_bearing)

    from .datasets.paderborn import OPERATING_CONDITIONS, TASKS

    pb = sub.add_parser("paderborn", help="Paderborn KAt bearing data (local files only)")
    pb_sub = pb.add_subparsers(dest="paderborn_command", required=True)
    pb_index = pb_sub.add_parser("index", help="list recognised files and task coverage")
    pb_index.add_argument("root", type=Path, help="folder containing the extracted .mat files")
    pb_index.add_argument("--out", help="optional CSV path for the file index")
    pb_index.set_defaults(func=_cmd_paderborn_index)
    pb_verify = pb_sub.add_parser(
        "verify", help="check archive MD5s and that every measurement was extracted"
    )
    pb_verify.add_argument("root", type=Path, help="folder containing the extracted .mat files")
    pb_verify.add_argument("--archives", type=Path, help="folder with the downloaded .rar files")
    pb_verify.add_argument("--task", choices=sorted(TASKS), default="real3")
    pb_verify.add_argument(
        "--source", choices=("zenodo", "original"), default="zenodo",
        help="where the archives came from (the MD5 manifest is the Zenodo mirror's)",
    )  # fmt: skip
    pb_verify.set_defaults(func=_cmd_paderborn_verify)
    pb_inspect = pb_sub.add_parser("inspect", help="show the channels inside one .mat file")
    pb_inspect.add_argument("file", type=Path)
    pb_inspect.set_defaults(func=_cmd_paderborn_inspect)
    pb_feats = pb_sub.add_parser("features", help="segment recordings and extract features")
    pb_feats.add_argument("root", type=Path, help="folder containing the extracted .mat files")
    pb_feats.add_argument("--task", choices=sorted(TASKS), default="real3")
    pb_feats.add_argument("--out", default="outputs/paderborn_features.csv")
    pb_feats.add_argument("--segment-seconds", type=float, default=1.0)
    pb_feats.add_argument("--conditions", nargs="+", choices=sorted(OPERATING_CONDITIONS))
    pb_feats.add_argument(
        "--max-measurements", type=int, help="use only measurements 1..N per setting (quick runs)"
    )
    pb_feats.add_argument(
        "--envelope-band", type=float, nargs=2, metavar=("LOW_HZ", "HIGH_HZ"),
        help="demodulation band for envelope analysis (default 0.1-0.4 fs)",
    )  # fmt: skip
    pb_feats.add_argument(
        "--expected-duration", type=float, default=4.0,
        help="nominal recording length in s for the integrity check (0 disables)",
    )  # fmt: skip
    pb_feats.set_defaults(func=_cmd_paderborn_features)

    bench = sub.add_parser("benchmark", help="leakage-safe benchmark of baselines and models")
    bench.add_argument("features", nargs="?", help="feature table CSV (e.g. from paderborn)")
    bench.add_argument("--synthetic", action="store_true", help="dry run on synthetic data")
    bench.add_argument("--out", default="outputs/benchmark")
    bench.add_argument("--n-splits", type=int, default=5)
    bench.add_argument("--n-boot", type=int, default=1000)
    bench.add_argument("--seed", type=int, default=0)
    bench.add_argument(
        "--learned",
        action="store_true",
        help="also evaluate logistic regression and a random forest (needs the [ml] extra)",
    )
    bench.set_defaults(func=_cmd_benchmark)

    from .leakage import SPLIT_MODELS

    leak = sub.add_parser("leakage", help="same model under a random split vs a group split")
    leak.add_argument("features", nargs="?", help="feature table CSV with label and group columns")
    leak.add_argument("--synthetic", action="store_true", help="run on a synthetic table")
    leak.add_argument(
        "--severity", type=float, nargs=2, default=(0.05, 0.15), metavar=("LOW", "HIGH"),
        help="synthetic fault severity range (default 0.05 0.15: subtle faults)",
    )  # fmt: skip
    leak.add_argument("--machines", type=int, default=6, help="synthetic machines per class")
    leak.add_argument("--segments", type=int, default=6, help="synthetic segments per machine")
    leak.add_argument(
        "--models", nargs="+", choices=SPLIT_MODELS,
        help="models to compare (default: all that can be imported)",
    )  # fmt: skip
    leak.add_argument("--label-col", default="label")
    leak.add_argument("--group-col", default="group_id")
    leak.add_argument("--repeats", type=int, default=5, help="repeats with different fold seeds")
    leak.add_argument("--n-splits", type=int, default=5)
    leak.add_argument("--seed", type=int, default=0)
    leak.add_argument("--out", default="outputs/leakage")
    leak.set_defaults(func=_cmd_leakage)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    custom = [getattr(args, k, None) for k in ("n_elements", "ball_mm", "pitch_mm")]
    if any(v is not None for v in custom) and not all(v is not None for v in custom):
        parser.error("custom bearing needs --n-elements, --ball-mm and --pitch-mm together")
    try:
        code: int = args.func(args)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        parser.exit(2, f"pumpguard: error: {exc}\n")
    return code
