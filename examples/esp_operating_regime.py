"""Synthetic ESP operating-regime sweep: consistent operating points vs naive scaling.

Uses an INVENTED pump curve and well (pumpguard.regime.illustrative_*). The point
is the method, not the numbers: at each drive frequency the operating point is the
intersection of the speed-scaled pump curve with the well's system curve. Scaling
one measured point with Q ~ f and dp ~ f^2 gives points that do not satisfy the
system curve.

Usage:
    python examples/esp_operating_regime.py --out outputs/esp_operating_regime.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from pumpguard.orders import rpm_from_supply_frequency
from pumpguard.plotting import GRID, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY
from pumpguard.regime import (
    illustrative_esp,
    illustrative_well,
    naive_affinity_projection,
    speed_sweep,
)
from pumpguard.units import m3s_to_bpd

FREQS_HZ = (45, 50, 55, 60)
REFERENCE_HZ = 50
# Ordinal blue ramp (reference palette steps 250 -> 700) for increasing speed.
RAMP = ("#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
NAIVE = "#eb6834"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("outputs/esp_operating_regime.png"))
    args = parser.parse_args()

    pump, well = illustrative_esp(), illustrative_well()
    speeds = [rpm_from_supply_frequency(f) for f in FREQS_HZ]
    solved = speed_sweep(pump, well, speeds)
    naive = naive_affinity_projection(pump, well, rpm_from_supply_frequency(REFERENCE_HZ), speeds)
    print(solved[["speed_rpm", "flow_bpd", "head_m", "relative_flow", "in_operating_range"]])
    print(naive[["speed_rpm", "flow_bpd_naive", "flow_bpd_solved", "system_head_gap_m"]])

    fig = Figure(figsize=(10, 6.2), layout="constrained", facecolor=SURFACE)
    ax = fig.subplots()
    ax.set_facecolor(SURFACE)
    q_sys_max = 0.0
    for f_hz, speed, color in zip(FREQS_HZ, speeds, RAMP, strict=True):
        lo, hi = pump.flow_range_m3_s(speed)
        q = np.linspace(lo, hi, 200)
        h = [pump.head_m(x, speed) for x in q]
        ax.plot(m3s_to_bpd(q), h, color=color, linewidth=2)
        ax.annotate(
            f"{f_hz} Hz",
            (m3s_to_bpd(q[-1]), h[-1]),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=TEXT_SECONDARY,
        )
        q_sys_max = max(q_sys_max, hi)
    q_sys = np.linspace(0.0, q_sys_max, 200)
    ax.plot(
        m3s_to_bpd(q_sys),
        [well.required_head_m(x) for x in q_sys],
        color=TEXT_PRIMARY,
        linewidth=2,
        linestyle=(0, (6, 3)),
        label="well system curve (required head)",
    )
    ok = solved[solved["feasible"]]
    ax.scatter(
        ok["flow_bpd"],
        ok["head_m"],
        s=70,
        color=TEXT_PRIMARY,
        zorder=5,
        edgecolors=SURFACE,
        linewidths=2,
        label="operating point (intersection)",
    )
    ax.scatter(
        naive["flow_bpd_naive"],
        naive["head_m_naive"],
        s=70,
        facecolors="none",
        edgecolors=NAIVE,
        linewidths=2,
        zorder=5,
        label=f"naive Q~f, H~f² from the {REFERENCE_HZ} Hz point",
    )

    ax.set_title(
        "Synthetic ESP: operating point = pump curve ∩ system curve",
        loc="left",
        fontsize=12,
        color=TEXT_PRIMARY,
    )
    ax.set_xlabel("Total liquid flow (BPD)", color=TEXT_SECONDARY)
    ax.set_ylabel("Head (m)", color=TEXT_SECONDARY)
    ax.set_xlim(0, m3s_to_bpd(q_sys_max) * 1.08)
    ax.set_ylim(bottom=0)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="lower left")
    fig.text(
        0.01,
        -0.03,
        "Invented pump curve and well, for illustration only. Not a catalog curve, not field data.",
        fontsize=8,
        color=TEXT_SECONDARY,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
