"""Command-line interface: ``pumpguard <command> [options]``.

Commands:
    demo      generate one synthetic signal, print features, save CSV/JSON/PNG
    features  compute features for any signal CSV (time_s, vibration)
    dataset   build a labelled synthetic feature table
    bearing   print bearing defect frequencies for a shaft speed
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    custom = [getattr(args, k, None) for k in ("n_elements", "ball_mm", "pitch_mm")]
    if any(v is not None for v in custom) and not all(v is not None for v in custom):
        parser.error("custom bearing needs --n-elements, --ball-mm and --pitch-mm together")
    try:
        code: int = args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(2, f"pumpguard: error: {exc}\n")
    return code
