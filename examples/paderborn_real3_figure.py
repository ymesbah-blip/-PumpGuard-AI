"""Figure for the Paderborn real3 results: envelope physics per bearing, and the leakage gap.

Left: median envelope-peak ratios at BPFO and BPFI for each of the 15 bearings (faint dots:
every 1 s segment). Right: diagnosis balanced accuracy of each model on unseen bearings
(group k-fold, with 95 % group-bootstrap interval) vs a random segment split.

Needs the outputs of:
    pumpguard paderborn features DATA --task real3 --out outputs/pu_real3.csv
    pumpguard benchmark outputs/pu_real3.csv --learned --out outputs/bench_real3

Usage:
    python examples/paderborn_real3_figure.py --features outputs/pu_real3.csv \
        --bench outputs/bench_real3/results.json --out docs/images/paderborn_real3.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from pumpguard.plotting import GRID, GUIDE, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY

CLASS_COLORS = {"healthy": "#2a78d6", "outer": "#eb6834", "inner": "#1baf7a"}  # slots 1-3
# Label offsets (points) for the crowded low-ratio cluster; others go to the right.
LABEL_OFFSET = {
    "K001": (-8, 6, "right"), "K003": (-8, -10, "right"), "K004": (9, -1, "left"),
    "K005": (-8, 8, "right"), "KA22": (8, -12, "left"), "K002": (7, -9, "left"),
    "KA15": (-8, 4, "right"), "KA30": (8, 5, "left"), "KA16": (-8, 6, "right"),
    "KI04": (-8, 4, "right"), "KI14": (7, -4, "left"),
}  # fmt: skip
GROUP_COLOR, RANDOM_COLOR = "#2a78d6", "#eb6834"


def _style(ax) -> None:  # type: ignore[no-untyped-def]
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, default=Path("outputs/pu_real3.csv"))
    parser.add_argument("--bench", type=Path, default=Path("outputs/bench_real3/results.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/images/paderborn_real3.png"))
    args = parser.parse_args()

    df = pd.read_csv(args.features)
    results = json.loads(args.bench.read_text(encoding="utf-8"))["results"]
    med = df.groupby(["group_id", "label"])[["env_bpfo_ratio", "env_bpfi_ratio"]].median()
    med = med.reset_index()

    fig = Figure(figsize=(13, 5.6), layout="constrained", facecolor=SURFACE)
    ax1, ax2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.15, 1]})

    # Left: envelope physics per bearing.
    _style(ax1)
    for label, color in CLASS_COLORS.items():
        seg = df[df["label"] == label]
        ax1.scatter(seg["env_bpfo_ratio"], seg["env_bpfi_ratio"], s=4, color=color, alpha=0.12,
                    linewidths=0, rasterized=True)  # fmt: skip
    lim = (1.0, 35.0)
    ax1.plot(lim, lim, color=GUIDE, linewidth=1, linestyle=(0, (2, 3)))
    ax1.annotate("BPFO = BPFI", (26, 26), xytext=(-4, 4), textcoords="offset points",
                 ha="right", fontsize=8, color=TEXT_SECONDARY, rotation=38)  # fmt: skip
    for label, color in CLASS_COLORS.items():
        sub = med[med["label"] == label]
        ax1.scatter(sub["env_bpfo_ratio"], sub["env_bpfi_ratio"], s=64, color=color,
                    edgecolors=SURFACE, linewidths=2, zorder=5, label=label)  # fmt: skip
        for r in sub.itertuples(index=False):
            dx, dy, ha = LABEL_OFFSET.get(r.group_id, (7, 2, "left"))
            ax1.annotate(r.group_id, (r.env_bpfo_ratio, r.env_bpfi_ratio), xytext=(dx, dy),
                         textcoords="offset points", fontsize=8, color=TEXT_PRIMARY,
                         ha=ha)  # fmt: skip
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlim(*lim)
    ax1.set_ylim(*lim)
    ax1.set_xlabel("Envelope peak ratio at BPFO (outer race)", color=TEXT_SECONDARY)
    ax1.set_ylabel("Envelope peak ratio at BPFI (inner race)", color=TEXT_SECONDARY)
    ax1.set_title("Envelope peaks per bearing (median; faint: 1 s segments)", loc="left",
                  fontsize=11, color=TEXT_PRIMARY)  # fmt: skip
    ax1.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="upper left")

    # Right: unseen bearings vs random segments, diagnosis task.
    _style(ax2)
    rows = results["tasks"]["diagnosis"]
    leak = results.get("leakage_check", {})
    names = [r["baseline"] for r in rows if r["baseline"] != "majority_class"]
    for i, name in enumerate(names):
        r = next(x for x in rows if x["baseline"] == name)
        g = r["metrics"]["balanced_accuracy"]
        lo, hi = r["ci95"]["balanced_accuracy"]
        rnd = leak.get(f"diagnosis/{name}", {}).get("random_segment_kfold_balanced_accuracy")
        ax2.plot([lo, hi], [i, i], color=GROUP_COLOR, linewidth=2, alpha=0.35,
                 solid_capstyle="round")  # fmt: skip
        if rnd is not None:
            ax2.plot([g, rnd], [i, i], color=GUIDE, linewidth=1, linestyle=(0, (2, 2)))
            leaky_label = "random segment split (leaky)" if i == 0 else None
            ax2.scatter([rnd], [i], s=64, color=RANDOM_COLOR, edgecolors=SURFACE, linewidths=2,
                        zorder=5, label=leaky_label)  # fmt: skip
            ax2.annotate(f"{rnd:.2f}", (rnd, i), xytext=(0, 8), textcoords="offset points",
                         ha="center", fontsize=8, color=TEXT_SECONDARY)  # fmt: skip
        group_label = "unseen bearings (group k-fold, 95 % CI)" if i == 0 else None
        ax2.scatter([g], [i], s=64, color=GROUP_COLOR, edgecolors=SURFACE, linewidths=2,
                    zorder=6, label=group_label)  # fmt: skip
        ax2.annotate(f"{g:.2f}", (g, i), xytext=(0, -13), textcoords="offset points",
                     ha="center", fontsize=8, color=TEXT_SECONDARY)  # fmt: skip
    chance = 1 / 3
    ax2.axvline(chance, color=GUIDE, linewidth=1, linestyle=(0, (2, 3)))
    ax2.annotate("chance", (chance, len(names) - 0.5), xytext=(4, 0), textcoords="offset points",
                 fontsize=8, color=TEXT_SECONDARY)  # fmt: skip
    ax2.set_yticks(range(len(names)), [n.replace("_", " ") for n in names])
    ax2.set_ylim(-0.7, len(names) - 0.3)
    ax2.invert_yaxis()
    ax2.set_xlim(0.2, 1.05)
    ax2.set_xlabel("Diagnosis balanced accuracy (healthy / outer / inner)", color=TEXT_SECONDARY)
    ax2.set_title("Same model, two protocols", loc="left", fontsize=11, color=TEXT_PRIMARY)
    ax2.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="lower right")

    fig.suptitle(
        "Paderborn real3: 15 real bearings, 4 765 segments. Physics is visible; leakage is large.",
        x=0.01, ha="left", fontsize=12, color=TEXT_PRIMARY,
    )  # fmt: skip
    fig.text(
        0.01, -0.04,
        "Bearing test rig (Lessmeier et al. 2016, CC BY-NC 4.0), not a centrifugal pump. "
        "Files from the Zenodo mirror, MD5-verified. Group k-fold by bearing, k = 5, seed 0.",
        fontsize=8, color=TEXT_SECONDARY,
    )  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
