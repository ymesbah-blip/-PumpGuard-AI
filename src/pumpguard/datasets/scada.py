"""Typed loader for low-rate SCADA trend data (e.g. ESP controller logs).

A schema declares, for every column, the physical quantity and the unit it is
logged in. The loader converts to SI, checks that values are finite, timestamps
increase and the logging interval matches what was declared, and reports gaps.

Two cautions specific to SCADA trends:

* They are **slow** (often one value per minute). Vibration channels are overall
  levels, so shaft orders, vane pass and bearing defect frequencies are not
  observable in them (see :mod:`pumpguard.sensors`).
* Consecutive records are strongly autocorrelated. Random record-level
  train/test splits leak; use :func:`time_block_split`.

Field data are often confidential. Keep them out of the repository (``data/`` is
git-ignored) and out of shared reports unless the owner agrees.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..units import BBL_M3, PSI_PA, STANDARD_GRAVITY

__all__ = [
    "UNITS",
    "ChannelSpec",
    "ScadaError",
    "ScadaSchema",
    "load_scada_csv",
    "time_block_split",
]


class ScadaError(ValueError):
    """Schema or data problem in a SCADA file."""


def _scale(factor: float) -> Callable[[pd.Series], pd.Series]:
    return lambda s: s * factor


#: quantity -> {logged unit -> (SI unit, converter)}
UNITS: dict[str, dict[str, tuple[str, Callable[[pd.Series], pd.Series]]]] = {
    "pressure": {
        "Pa": ("Pa", _scale(1.0)),
        "kPa": ("Pa", _scale(1e3)),
        "MPa": ("Pa", _scale(1e6)),
        "bar": ("Pa", _scale(1e5)),
        "psi": ("Pa", _scale(PSI_PA)),
    },
    "temperature": {
        "degC": ("degC", _scale(1.0)),
        "K": ("degC", lambda s: s - 273.15),
        "degF": ("degC", lambda s: (s - 32.0) * 5.0 / 9.0),
    },
    "acceleration": {"m/s^2": ("m/s^2", _scale(1.0)), "g": ("m/s^2", _scale(STANDARD_GRAVITY))},
    "velocity": {"m/s": ("m/s", _scale(1.0)), "mm/s": ("m/s", _scale(1e-3))},
    "flow": {
        "m3/s": ("m3/s", _scale(1.0)),
        "m3/d": ("m3/s", _scale(1.0 / 86_400.0)),
        "bpd": ("m3/s", _scale(BBL_M3 / 86_400.0)),
    },
    "frequency": {"Hz": ("Hz", _scale(1.0))},
    "speed": {"rpm": ("rpm", _scale(1.0))},
    "current": {"A": ("A", _scale(1.0))},
    "voltage": {"V": ("V", _scale(1.0))},
    "power": {"W": ("W", _scale(1.0)), "kW": ("W", _scale(1e3))},
    "dimensionless": {"1": ("1", _scale(1.0)), "%": ("1", _scale(0.01))},
}


@dataclass(frozen=True)
class ChannelSpec:
    """One logged column: source column name, output name, quantity and logged unit."""

    column: str
    name: str
    quantity: str
    unit: str

    def __post_init__(self) -> None:
        if self.quantity not in UNITS:
            raise ScadaError(
                f"{self.column}: unknown quantity {self.quantity!r}; use {sorted(UNITS)}"
            )
        if self.unit not in UNITS[self.quantity]:
            raise ScadaError(
                f"{self.column}: unit {self.unit!r} not supported for {self.quantity}; "
                f"use {sorted(UNITS[self.quantity])}"
            )
        if not self.name.isidentifier():
            raise ScadaError(f"output name {self.name!r} must be a valid identifier")

    @property
    def si_unit(self) -> str:
        return UNITS[self.quantity][self.unit][0]


@dataclass(frozen=True)
class ScadaSchema:
    time_column: str
    channels: tuple[ChannelSpec, ...]
    expected_interval_s: float | None = None
    interval_tolerance: float = 0.25
    time_format: str | None = None
    dayfirst: bool = False

    def __post_init__(self) -> None:
        if not self.channels:
            raise ScadaError("schema needs at least one channel")
        names = [c.name for c in self.channels]
        if len(set(names)) != len(names):
            raise ScadaError("channel output names must be unique")
        if self.expected_interval_s is not None and not (
            math.isfinite(self.expected_interval_s) and self.expected_interval_s > 0
        ):
            raise ScadaError("expected_interval_s must be positive")
        if not 0 < self.interval_tolerance < 1:
            raise ScadaError("interval_tolerance must be in (0, 1)")


def load_scada_csv(
    path: str | Path,
    schema: ScadaSchema,
    *,
    drop_nonfinite: bool = False,
    gap_factor: float = 5.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read, validate and convert a SCADA CSV to SI units.

    Returns ``(data, report)``. ``data`` has a ``time`` column plus one column per
    channel (named ``ChannelSpec.name``, SI units listed in ``report['units']``).
    """
    p = Path(path)
    raw = pd.read_csv(p)
    needed = [schema.time_column, *(c.column for c in schema.channels)]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise ScadaError(f"{p.name}: missing column(s) {missing}; found {list(raw.columns)}")

    try:
        time = pd.to_datetime(
            raw[schema.time_column], format=schema.time_format, dayfirst=schema.dayfirst
        )
    except (ValueError, TypeError) as exc:
        raise ScadaError(f"{p.name}: cannot parse time column: {exc}") from exc
    data = pd.DataFrame({"time": time})
    for ch in schema.channels:
        values = pd.to_numeric(raw[ch.column], errors="coerce").astype(float)
        data[ch.name] = UNITS[ch.quantity][ch.unit][1](values)

    report: dict[str, Any] = {"source_file": p.name, "n_rows_raw": len(data)}
    finite = np.isfinite(data[[c.name for c in schema.channels]].to_numpy()).all(axis=1)
    finite &= data["time"].notna().to_numpy()
    n_bad = int((~finite).sum())
    if n_bad and not drop_nonfinite:
        per_col = {c.name: int((~np.isfinite(data[c.name])).sum()) for c in schema.channels}
        raise ScadaError(
            f"{p.name}: {n_bad} row(s) with missing/non-numeric values {per_col}; "
            "fix the export or pass drop_nonfinite=True (rows are then dropped and reported)"
        )
    data = data.loc[finite]
    report["n_rows_dropped_nonfinite"] = n_bad

    data = data.sort_values("time", kind="stable")
    dup = data["time"].duplicated(keep="first")
    report["n_duplicate_timestamps_dropped"] = int(dup.sum())
    data = data.loc[~dup].reset_index(drop=True)
    if len(data) < 2:
        raise ScadaError(f"{p.name}: fewer than two valid records")

    dt = data["time"].diff().dt.total_seconds().to_numpy()[1:]
    median = float(np.median(dt))
    if schema.expected_interval_s is not None:
        rel = abs(median - schema.expected_interval_s) / schema.expected_interval_s
        if rel > schema.interval_tolerance:
            raise ScadaError(
                f"{p.name}: median logging interval {median:g} s differs from the declared "
                f"{schema.expected_interval_s:g} s"
            )
    gaps = dt > gap_factor * median
    report.update(
        n_rows=len(data),
        start=str(data["time"].iloc[0]),
        end=str(data["time"].iloc[-1]),
        median_interval_s=median,
        sample_rate_hz=1.0 / median,
        n_gaps=int(gaps.sum()),
        largest_gap_s=float(dt.max()),
        units={c.name: c.si_unit for c in schema.channels},
        logged_units={c.name: c.unit for c in schema.channels},
    )
    return data, report


def time_block_split(
    data: pd.DataFrame,
    *,
    time_column: str = "time",
    block: str = "1D",
    test_fraction: float = 0.2,
    mode: str = "chronological",
    embargo_blocks: int = 0,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split time-series records by whole time blocks (default: days).

    ``mode="chronological"`` (default) holds out the last blocks, the honest
    choice for anything used to forecast. ``mode="random"`` picks random blocks.
    ``embargo_blocks`` drops that many blocks next to every test block from the
    training set, to limit autocorrelation leaking across the boundary.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be in (0, 1)")
    if mode not in ("chronological", "random"):
        raise ValueError("mode must be 'chronological' or 'random'")
    if embargo_blocks < 0:
        raise ValueError("embargo_blocks must be >= 0")
    blocks = pd.to_datetime(data[time_column]).dt.floor(block)
    unique = np.array(sorted(blocks.unique()))
    if unique.size < 2:
        raise ValueError("need at least two time blocks to split")
    n_test = max(1, round(unique.size * test_fraction))
    if mode == "chronological":
        test_idx = np.arange(unique.size - n_test, unique.size)
    else:
        test_idx = np.sort(np.random.default_rng(seed).choice(unique.size, n_test, replace=False))
    excluded = set(test_idx.tolist())
    for i in (int(k) for k in test_idx):
        excluded.update(range(max(0, i - embargo_blocks), min(unique.size, i + embargo_blocks + 1)))
    test_blocks = set(unique[test_idx])
    train_blocks = {b for j, b in enumerate(unique) if j not in excluded}
    is_test = blocks.isin(test_blocks)
    is_train = blocks.isin(train_blocks)
    return data.loc[is_train].reset_index(drop=True), data.loc[is_test].reset_index(drop=True)
