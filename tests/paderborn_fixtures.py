"""Small, INVENTED stand-ins for Paderborn KAt .mat files.

Nothing here is Paderborn data. The files mimic the published layout (one
top-level struct named after the file, a ``Y`` struct array of channels with
``Name``, ``Type``, ``Unit``, ``Data``, ``Raster``) with synthetic content and
short durations, so tests run in seconds without any third-party data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.io as sio

from pumpguard import BearingGeometry, SignalConfig, simulate

FIXTURE_DURATION_S = 0.25
_CONDITION = {"healthy": "healthy", "outer": "bearing_outer", "inner": "bearing_inner"}
_LABEL_OF_PREFIX = {"K0": "healthy", "KA": "outer", "KI": "inner", "KB": "outer"}


def write_mat(
    path: Path,
    *,
    seed: int = 0,
    duration: float = FIXTURE_DURATION_S,
    speed_rpm: float | None = None,
    include_speed: bool = True,
    vibration_unit: str = "m/s^2",
    drop_vibration: bool = False,
) -> Path:
    """Write one invented file. Name must follow N.._M.._F.._<bearing>_<n>.mat."""
    stem = path.stem
    condition_code, bearing = stem[:11], stem.split("_")[3]
    nominal = 900.0 if condition_code.startswith("N09") else 1500.0
    label = _LABEL_OF_PREFIX[bearing[:2]]
    sig = simulate(
        SignalConfig(
            condition=_CONDITION[label],
            fs=64_000.0,
            duration=duration,
            rpm=nominal,
            seed=seed,
            bearing=BearingGeometry.from_preset("6203"),
            resonance_hz=8_000.0,
            n_vanes=1,
        )
    )
    n_mech = int(4_000 * duration)
    rng = np.random.default_rng(seed + 1)
    channels = [
        ("force", "N", rng.normal(1000.0, 5.0, n_mech), "Mech_4kHz"),
        ("phase_current_1", "A", rng.normal(0, 1, sig.x.size).astype(np.float32), "HostService"),
        ("phase_current_2", "A", rng.normal(0, 1, sig.x.size).astype(np.float32), "HostService"),
        ("temp_2_bearing_module", "degC", np.array([45.0]), "Temp"),
        ("torque", "Nm", rng.normal(0.7, 0.01, n_mech), "Mech_4kHz"),
    ]
    if include_speed:
        value = nominal * 0.995 if speed_rpm is None else speed_rpm
        channels.append(("speed", "rpm", rng.normal(value, 2.0, n_mech), "Mech_4kHz"))
    if not drop_vibration:
        channels.append(("vibration_1", vibration_unit, sig.x, "HostService"))

    dtype = [("Name", "O"), ("Type", "O"), ("Unit", "O"), ("Data", "O"), ("Raster", "O")]
    y = np.zeros((1, len(channels)), dtype=dtype)
    for i, (name, unit, data, raster) in enumerate(channels):
        y[0, i] = (name, "invented", unit, np.asarray(data).reshape(1, -1), raster)
    payload = {
        "Info": "INVENTED TEST FIXTURE - not Paderborn data",
        "X": np.zeros((1, 0)),
        "Y": y,
        "Description": "pumpguard test fixture",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(str(path), {stem: payload})
    return path


def write_dataset(
    root: Path,
    bearings: list[str],
    *,
    condition: str = "N15_M07_F10",
    measurements: int = 2,
) -> list[Path]:
    """Write ``measurements`` invented files per bearing in per-bearing folders."""
    paths = []
    for b_i, bearing in enumerate(bearings):
        for m in range(1, measurements + 1):
            path = root / bearing / f"{condition}_{bearing}_{m}.mat"
            paths.append(write_mat(path, seed=100 * b_i + m))
    return paths
