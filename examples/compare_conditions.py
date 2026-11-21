"""Which features separate which synthetic condition?

Builds a small labelled synthetic dataset and draws one strip chart per feature,
so you can see, for example, that RMS separates imbalance but not bearing
defects, while envelope ratios separate bearing defects cleanly.

These are synthetic signals built to show these patterns, so the separation here
says nothing about performance on real machines.

Usage:
    python examples/compare_conditions.py --out outputs/feature_separation.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from pumpguard import CONDITIONS
from pumpguard.dataset import make_synthetic_dataset
from pumpguard.plotting import GRID, SERIES, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY

FEATURES = [
    ("rms", "RMS", "linear"),
    ("kurtosis", "Kurtosis", "linear"),
    ("amp_2x", "2x amplitude", "linear"),
    ("env_bpfo_ratio", "Envelope BPFO ratio", "log"),
    ("env_bpfi_ratio", "Envelope BPFI ratio", "log"),
    ("hf_energy_ratio", "High-frequency energy ratio", "linear"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("outputs/feature_separation.png"))
    parser.add_argument("--machines", type=int, default=4)
    parser.add_argument("--segments", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    df = make_synthetic_dataset(
        machines_per_condition=args.machines,
        segments_per_machine=args.segments,
        seed=args.seed,
    )
    conditions = list(CONDITIONS)
    rng = np.random.default_rng(0)

    fig = Figure(figsize=(12, 7), layout="constrained", facecolor=SURFACE)
    fig.suptitle(
        f"Feature values by condition — synthetic data ({len(df)} segments, "
        f"{df['group_id'].nunique()} virtual machines)",
        x=0.01,
        ha="left",
        fontsize=13,
        color=TEXT_PRIMARY,
    )
    axes = fig.subplots(2, 3, sharey=True).ravel()
    for ax, (column, label, scale) in zip(axes, FEATURES, strict=True):
        for row, condition in enumerate(conditions):
            values = df.loc[df["condition"] == condition, column].to_numpy()
            jitter = rng.uniform(-0.18, 0.18, values.size)
            ax.scatter(values, row + jitter, s=16, color=SERIES, alpha=0.55, linewidths=0)
            ax.plot(
                [np.median(values)] * 2, [row - 0.3, row + 0.3], color=TEXT_PRIMARY, linewidth=1.5
            )
        ax.set_xscale(scale)
        ax.set_title(label, loc="left", fontsize=11, color=TEXT_PRIMARY)
        ax.set_yticks(range(len(conditions)), conditions)
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
        ax.grid(True, axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
    axes[0].invert_yaxis()  # shared y-axis: first condition on top in every panel
    fig.text(
        0.01,
        -0.02,
        "Dots = segments, black tick = median. Synthetic signals are built to show these "
        "patterns; this is not evidence of real-world performance.",
        fontsize=8,
        color=TEXT_SECONDARY,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
