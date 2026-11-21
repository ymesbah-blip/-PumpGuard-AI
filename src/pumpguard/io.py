"""Reading and writing signals as CSV with a JSON metadata sidecar.

CSV schema: two columns, ``time_s`` (seconds) and ``vibration`` (any unit).
Sidecar: ``<name>.json`` next to the CSV holding provenance metadata. Synthetic
signals always carry ``"synthetic": true`` so they cannot be mistaken for
measurements once shared.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from ._validation import FloatArray, as_signal

__all__ = ["SIGNAL_COLUMNS", "LoadedSignal", "load_signal", "save_signal"]

SIGNAL_COLUMNS: tuple[str, str] = ("time_s", "vibration")


@dataclass(frozen=True)
class LoadedSignal:
    t: FloatArray
    x: FloatArray
    fs: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _json_default(obj: object) -> object:
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"{type(obj).__name__} is not JSON serialisable")


def save_signal(
    path: str | Path,
    t: ArrayLike,
    x: ArrayLike,
    metadata: dict[str, Any] | None = None,
) -> tuple[Path, Path | None]:
    """Write ``t`` and ``x`` to CSV, plus ``metadata`` to a ``.json`` sidecar if given."""
    t_arr = as_signal(t, "t")
    x_arr = as_signal(x, "x")
    if t_arr.size != x_arr.size:
        raise ValueError("t and x must have the same length")
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({SIGNAL_COLUMNS[0]: t_arr, SIGNAL_COLUMNS[1]: x_arr}).to_csv(csv_path, index=False)
    sidecar: Path | None = None
    if metadata is not None:
        sidecar = csv_path.with_suffix(".json")
        sidecar.write_text(
            json.dumps(metadata, indent=2, default=_json_default) + "\n", encoding="utf-8"
        )
    return csv_path, sidecar


def load_signal(path: str | Path, fs: float | None = None) -> LoadedSignal:
    """Read a signal CSV (and its sidecar, if present).

    The sampling rate is taken from ``fs``, then the sidecar's ``"fs"``, then
    inferred from a uniformly spaced ``time_s`` column.
    """
    csv_path = Path(path)
    df = pd.read_csv(csv_path)
    missing = [c for c in SIGNAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing column(s) {missing}; expected {SIGNAL_COLUMNS}")
    t = as_signal(df[SIGNAL_COLUMNS[0]].to_numpy(dtype=float), "time_s")
    x = as_signal(df[SIGNAL_COLUMNS[1]].to_numpy(dtype=float), "vibration")

    sidecar = csv_path.with_suffix(".json")
    metadata: dict[str, Any] = (
        json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    )

    if fs is None:
        fs = metadata.get("fs")
    if fs is None:
        if t.size < 2:
            raise ValueError("cannot infer fs from fewer than two samples; pass fs explicitly")
        dt = np.diff(t)
        if np.any(dt <= 0) or not np.allclose(dt, dt.mean(), rtol=1e-3):
            raise ValueError("time_s is not uniformly increasing; pass fs explicitly")
        fs = 1.0 / float(np.median(dt))
    fs = float(fs)
    if not math.isfinite(fs) or fs <= 0:
        raise ValueError(f"invalid sampling rate {fs!r}")
    return LoadedSignal(t=t, x=x, fs=fs, metadata=metadata)
