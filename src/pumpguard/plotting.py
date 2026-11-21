"""Static figures (PNG) built with Matplotlib's object-oriented API.

No ``pyplot`` state machine is used, so plotting works headless (CI, servers)
without configuring a backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike

from ._validation import as_signal, require_positive
from .spectral import amplitude_spectrum, envelope_spectrum

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from .bearings import BearingGeometry

__all__ = ["plot_signal_overview"]

# Palette roles (reference data-viz palette, light mode).
SERIES = "#2a78d6"
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GUIDE = "#8a8984"
GRID = "#e6e5e1"


def _style(ax: Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=TEXT_PRIMARY)
    ax.set_xlabel(xlabel, color=TEXT_SECONDARY, fontsize=9)
    ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=9)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def _mark(ax: Axes, freq: float, label: str, xmax: float) -> None:
    """Dashed guide line with a direct text label (no extra series colours)."""
    if not 0 < freq < xmax:
        return
    ax.axvline(freq, color=GUIDE, linestyle=(0, (4, 3)), linewidth=0.9, zorder=1)
    ax.annotate(
        label,
        xy=(freq, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(3, -3),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color=TEXT_SECONDARY,
    )


def plot_signal_overview(
    t: ArrayLike,
    x: ArrayLike,
    fs: float,
    path: str | Path,
    *,
    title: str = "Vibration signal",
    rpm: float | None = None,
    n_vanes: int | None = None,
    bearing: BearingGeometry | None = None,
    envelope_band: tuple[float, float] | None = None,
    waveform_seconds: float = 0.25,
) -> Path:
    """Save a three-panel PNG: waveform, amplitude spectrum, envelope spectrum."""
    from matplotlib.figure import Figure

    t_arr = as_signal(t, "t")
    x_arr = as_signal(x, "x")
    fs = require_positive("fs", fs)

    fig = Figure(figsize=(10, 8.5), layout="constrained", facecolor=SURFACE)
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=TEXT_PRIMARY)
    ax_wave, ax_spec, ax_env = fig.subplots(3, 1)

    # 1) Waveform (first segment only, so impacts stay visible).
    keep = t_arr <= t_arr[0] + waveform_seconds
    ax_wave.plot(t_arr[keep], x_arr[keep], color=SERIES, linewidth=0.7)
    _style(ax_wave, f"Waveform (first {waveform_seconds:g} s)", "Time (s)", "Amplitude (a.u.)")

    # 2) Amplitude spectrum, log-log so shaft orders and high-frequency bands both show.
    freqs, amp = amplitude_spectrum(x_arr, fs)
    nyq = fs / 2
    sel = freqs >= 5.0
    ax_spec.loglog(freqs[sel], np.maximum(amp[sel], 1e-6), color=SERIES, linewidth=0.7)
    ax_spec.set_xlim(5.0, nyq)
    _style(ax_spec, "Amplitude spectrum", "Frequency (Hz)", "Amplitude (a.u.)")
    if rpm is not None:
        fr = rpm / 60.0
        _mark(ax_spec, fr, "1x", nyq)
        _mark(ax_spec, 2 * fr, "2x", nyq)
        if n_vanes is not None:
            _mark(ax_spec, n_vanes * fr, f"vane pass ({n_vanes}x)", nyq)

    # 3) Envelope spectrum around the bearing-defect range.
    env_f, env_a = envelope_spectrum(x_arr, fs, envelope_band)
    env_max = 600.0
    if rpm is not None and bearing is not None:
        defects = bearing.defect_frequencies(rpm)
        env_max = min(nyq, 3.5 * defects.bpfi)
    sel = (env_f > 0) & (env_f <= env_max)
    ax_env.plot(env_f[sel], env_a[sel], color=SERIES, linewidth=1.0)
    ax_env.set_xlim(0, env_max)
    ax_env.set_ylim(bottom=0)
    _style(ax_env, "Envelope spectrum", "Frequency (Hz)", "Amplitude (a.u.)")
    if rpm is not None and bearing is not None:
        _mark(ax_env, defects.bpfo, "BPFO", env_max)
        _mark(ax_env, defects.bpfi, "BPFI", env_max)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    return out
