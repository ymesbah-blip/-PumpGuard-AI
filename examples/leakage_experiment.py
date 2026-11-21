"""Synthetic leakage experiment: random-split vs group-split scores across fault severity.

Each virtual machine has its own speed and noise level, so its segments share a
"fingerprint" that has nothing to do with the fault. When faults are strong, every
split finds them. When faults are subtle, a random segment split lets the model
recognise machines it has already seen, and its score rises far above the
group-split score that actually measures generalisation.

Synthetic data only: the gap's size depends on the generator settings. The figure
shows the mechanism, not an estimate for any real dataset.

Usage:
    python examples/leakage_experiment.py --out outputs/leakage_vs_severity.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from matplotlib.figure import Figure

from pumpguard.benchmark import synthetic_feature_table
from pumpguard.leakage import SPLIT_MODELS, compare_splits
from pumpguard.models import sklearn_available
from pumpguard.plotting import GRID, GUIDE, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY

GROUP_COLOR = "#2a78d6"  # categorical slot 1
RANDOM_COLOR = "#eb6834"  # categorical slot 2
LEVELS = (0.03, 0.06, 0.12, 0.25, 0.5, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("outputs/leakage_vs_severity.png"))
    parser.add_argument("--levels", type=float, nargs="+", default=list(LEVELS))
    parser.add_argument("--machines", type=int, default=6, help="machines per class")
    parser.add_argument("--segments", type=int, default=6, help="segments per machine")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    models = [m for m in SPLIT_MODELS if m == "nearest_centroid" or sklearn_available()]
    curves: dict[str, dict[str, list[float]]] = {m: {"group": [], "random": []} for m in models}
    levels = sorted(args.levels)
    for level in levels:
        df = synthetic_feature_table(
            seed=args.seed,
            machines=args.machines,
            segments=args.segments,
            severity_range=(0.5 * level, 1.5 * level),
        )
        res = compare_splits(df, models=models, n_repeats=args.repeats, seed=args.seed)
        for m in models:
            s = res["models"][m]["summary"]
            curves[m]["group"].append(s["group_mean"])
            curves[m]["random"].append(s["random_mean"])
            print(
                f"severity {level:<5g} {m:<20} group {s['group_mean']:.3f}  "
                f"random {s['random_mean']:.3f}  inflation {s['inflation_mean']:+.3f}"
            )
    chance = res["chance_balanced_accuracy"]

    fig = Figure(figsize=(4 * len(models) + 1, 4.4), layout="constrained", facecolor=SURFACE)
    axes = fig.subplots(1, len(models), sharey=True, squeeze=False)[0]
    for ax, m in zip(axes, models, strict=True):
        ax.set_facecolor(SURFACE)
        ax.axhline(chance, color=GUIDE, linewidth=1, linestyle=(0, (2, 3)))
        ax.plot(levels, curves[m]["random"], color=RANDOM_COLOR, linewidth=2,
                linestyle=(0, (6, 3)), marker="o", markersize=7, markeredgecolor=SURFACE,
                markeredgewidth=2, label="random segment k-fold (leaky)")  # fmt: skip
        ax.plot(levels, curves[m]["group"], color=GROUP_COLOR, linewidth=2, marker="o",
                markersize=7, markeredgecolor=SURFACE, markeredgewidth=2,
                label="group k-fold (unseen machines)")  # fmt: skip
        ax.set_xscale("log")
        ax.set_xticks(levels, [f"{v:g}" for v in levels])
        ax.minorticks_off()
        ax.set_ylim(0, 1.05)
        ax.set_title(m.replace("_", " "), loc="left", fontsize=11, color=TEXT_PRIMARY)
        ax.set_xlabel("Fault severity (generator units)", color=TEXT_SECONDARY)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
        ax.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
    axes[0].set_ylabel("Balanced accuracy", color=TEXT_SECONDARY)
    axes[0].annotate("chance", (levels[-1], chance), xytext=(0, 4), textcoords="offset points",
                     ha="right", fontsize=8, color=TEXT_SECONDARY)  # fmt: skip
    axes[0].legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="lower right")
    fig.suptitle(
        "Synthetic: a random segment split overstates accuracy when faults are subtle",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TEXT_PRIMARY,
    )
    fig.text(
        0.01,
        -0.04,
        f"Synthetic healthy / outer / inner signals, {args.machines} machines per class, "
        f"{args.segments} segments each, mean of {args.repeats} fold seeds. "
        "Mechanism only, not an estimate for real data.",
        fontsize=8,
        color=TEXT_SECONDARY,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
