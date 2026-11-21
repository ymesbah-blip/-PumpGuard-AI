"""Reader for the Paderborn University KAt bearing dataset (local files only).

The data are **not** bundled or downloaded by PumpGuard AI. They are licensed
CC BY-NC 4.0 (non-commercial use, attribution required). Obtain them from the
original source, extract the archives, and point this module at the folder.

What this dataset is, and is not:

* Vibration and motor-current measurements of 6203 ball bearings in an
  electromechanical **bearing test rig**, at four operating points.
* It is **not** a centrifugal-pump dataset. Results on it say something about
  bearing-damage signatures in a controlled rig, not about pump diagnosis in
  the field.

Facts used here are taken from the dataset publication (Lessmeier et al., 2016)
and the KAt-DataCenter web pages. See ``docs/datasets/paderborn-kat.md``.

The ``.mat`` reader does not rely on hard-coded struct indices. It loads the
file with :func:`scipy.io.loadmat` (``simplify_cells=True``) and searches the
tree for channel records that have ``Name`` and ``Data`` fields, so it keeps
working if field order or nesting differs between files. Use
``pumpguard paderborn inspect FILE.mat`` to see what a file contains.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.io as sio

from .._validation import FloatArray
from .._version import __version__
from ..bearings import BearingGeometry
from ..features import extract_all_features
from .provenance import ProvenanceError, validate_provenance

__all__ = [
    "BEARINGS",
    "CHANNEL_RATES_HZ",
    "CITATION",
    "DATASET_ID",
    "LABELS",
    "LICENSE",
    "OPERATING_CONDITIONS",
    "SOURCE_URL",
    "TASKS",
    "BearingInfo",
    "OperatingCondition",
    "PaderbornError",
    "PaderbornFileError",
    "PaderbornFormatError",
    "PaderbornMeasurement",
    "TaskSpec",
    "build_feature_table",
    "inspect_file",
    "parse_filename",
    "read_measurement",
    "scan",
]

DATASET_ID = "paderborn-kat"
SOURCE_URL = "https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter"
LICENSE = "CC BY-NC 4.0"
CITATION = (
    "Lessmeier, C.; Kimotho, J. K.; Zimmer, D.; Sextro, W. (2016): Condition Monitoring of "
    "Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of "
    "Electric Motors: A Benchmark Data Set for Data-Driven Classification. European "
    "Conference of the Prognostics and Health Management Society, Bilbao (Spain). "
    "Data: Christian Lessmeier et al., KAt-DataCenter, Chair of Design and Drive Technology, "
    "Paderborn University."
)
MACHINE_TYPE = "electromechanical bearing test rig (not a centrifugal pump)"
NOMINAL_DURATION_S = 4.0

#: Sampling rates of the channels, from the dataset documentation.
CHANNEL_RATES_HZ: dict[str, float] = {
    "vibration_1": 64_000.0,
    "phase_current_1": 64_000.0,
    "phase_current_2": 64_000.0,
    "force": 4_000.0,
    "torque": 4_000.0,
    "speed": 4_000.0,
    "temp_2_bearing_module": 1.0,
}

_SENSORS: dict[str, tuple[str, str]] = {
    "vibration_1": (
        "PCB 336C04 piezoelectric accelerometer, Kistler 5015A charge amplifier (30 kHz low-pass)",
        "adapter at the top of the bearing module housing, main (radial) load direction",
    ),
}

#: Class labels used for this dataset.
LABELS: frozenset[str] = frozenset({"healthy", "outer", "inner", "outer+inner"})


class PaderbornError(ValueError):
    """Base class for problems with Paderborn files."""


class PaderbornFileError(PaderbornError):
    """A file exists but cannot be read (corrupt, unsupported MATLAB version, ...)."""


class PaderbornFormatError(PaderbornError):
    """A file name, structure, channel or duration does not match expectations."""


@dataclass(frozen=True)
class OperatingCondition:
    code: str
    rpm: float
    load_torque_nm: float
    radial_force_n: float


#: Operating conditions (Lessmeier et al. 2016, operating-conditions table).
OPERATING_CONDITIONS: dict[str, OperatingCondition] = {
    oc.code: oc
    for oc in (
        OperatingCondition("N15_M07_F10", 1500.0, 0.7, 1000.0),
        OperatingCondition("N09_M07_F10", 900.0, 0.7, 1000.0),
        OperatingCondition("N15_M01_F10", 1500.0, 0.1, 1000.0),
        OperatingCondition("N15_M07_F04", 1500.0, 0.7, 400.0),
    )
}


@dataclass(frozen=True)
class BearingInfo:
    code: str
    label: str
    damage_origin: str  # "none" | "artificial" | "real"
    damage: str
    extent: int | None = None


def _b(code: str, label: str, origin: str, damage: str, extent: int | None = None) -> BearingInfo:
    return BearingInfo(code, label, origin, damage, extent)


#: All 32 bearings (Lessmeier et al. 2016: healthy, artificial and real-damage tables).
BEARINGS: dict[str, BearingInfo] = {
    b.code: b
    for b in (
        *(_b(f"K00{i}", "healthy", "none", "undamaged (run-in)") for i in range(1, 7)),
        # Artificial damage, single point.
        _b("KA01", "outer", "artificial", "EDM", 1),
        _b("KA03", "outer", "artificial", "electric engraver", 2),
        _b("KA05", "outer", "artificial", "electric engraver", 1),
        _b("KA06", "outer", "artificial", "electric engraver", 2),
        _b("KA07", "outer", "artificial", "drilling", 1),
        _b("KA08", "outer", "artificial", "drilling", 2),
        _b("KA09", "outer", "artificial", "drilling", 2),
        _b("KI01", "inner", "artificial", "EDM", 1),
        _b("KI03", "inner", "artificial", "electric engraver", 1),
        _b("KI05", "inner", "artificial", "electric engraver", 1),
        _b("KI07", "inner", "artificial", "electric engraver", 2),
        _b("KI08", "inner", "artificial", "electric engraver", 2),
        # Real damage from accelerated lifetime tests.
        _b("KA04", "outer", "real", "fatigue: pitting", 1),
        _b("KA15", "outer", "real", "plastic deformation: indentations", 1),
        _b("KA16", "outer", "real", "fatigue: pitting", 2),
        _b("KA22", "outer", "real", "fatigue: pitting", 1),
        _b("KA30", "outer", "real", "plastic deformation: indentations", 1),
        _b("KB23", "outer+inner", "real", "fatigue: pitting (multiple)", 2),
        _b("KB24", "outer+inner", "real", "fatigue: pitting (multiple)", 3),
        _b("KB27", "outer+inner", "real", "plastic deformation: indentations (multiple)", 1),
        # KI04 and KI14: the fact sheets list a second damage, plastic deformation on the
        # outer ring ("multiple damage"). Labelled "inner" as in the publication.
        _b("KI04", "inner", "real", "fatigue: pitting (+ outer-ring indentation)", 1),
        _b("KI14", "inner", "real", "fatigue: pitting (+ outer-ring indentation)", 1),
        _b("KI16", "inner", "real", "fatigue: pitting", 3),
        _b("KI17", "inner", "real", "fatigue: pitting", 1),
        _b("KI18", "inner", "real", "fatigue: pitting", 2),
        _b("KI21", "inner", "real", "fatigue: pitting", 1),
    )
}

_PREFIX_LABEL = {"K0": "healthy", "KA": "outer", "KI": "inner", "KB": "outer+inner"}

_FILENAME_RE = re.compile(
    r"^(?P<condition>N\d{2}_M\d{2}_F\d{2})_(?P<bearing>K(?:\d{3}|[AIB]\d{2}))_(?P<index>\d{1,2})$"
)


@dataclass(frozen=True)
class TaskSpec:
    """A predefined, documented selection of bearings and how to split them.

    ``split`` maps bearing code -> "train"/"test". ``None`` means the benchmark
    uses group k-fold cross-validation over all selected bearings.
    """

    name: str
    description: str
    bearings: frozenset[str]
    split: dict[str, str] | None = None


_REAL3 = {
    "K001", "K002", "K003", "K004", "K005",
    "KA04", "KA15", "KA16", "KA22", "KA30",
    "KI04", "KI14", "KI16", "KI18", "KI21",
}  # fmt: skip
_ARTIFICIAL = {c for c, b in BEARINGS.items() if b.damage_origin == "artificial"}
_A2R_SPLIT = {
    **dict.fromkeys(("K001", "K002", "K003", *_ARTIFICIAL), "train"),
    **dict.fromkeys(
        ("K004", "K005", "K006", *(_REAL3 - {"K001", "K002", "K003", "K004", "K005"})), "test"
    ),
}

TASKS: dict[str, TaskSpec] = {
    "real3": TaskSpec(
        "real3",
        "Healthy vs real outer-race vs real inner-race damage: the 15 bearings of the "
        "real-damage experiment in Lessmeier et al. (2016). Group k-fold by bearing.",
        frozenset(_REAL3),
    ),
    "artificial_to_real": TaskSpec(
        "artificial_to_real",
        "Train on artificial damage (+ healthy K001-K003), test on real damage (+ healthy "
        "K004-K006). Measures transfer from lab-made to real damage. Split defined by this "
        "project, not taken from the paper.",
        frozenset(_A2R_SPLIT),
        _A2R_SPLIT,
    ),
    "all_single": TaskSpec(
        "all_single",
        "All bearings with a single damage location (excludes KB* combined damage). Group "
        "k-fold by bearing.",
        frozenset(c for c, b in BEARINGS.items() if b.label != "outer+inner"),
    ),
}

#: Geometry used for defect frequencies (8 balls, 6.75 mm, pitch 28.55 mm). The
#: publication notes 1-2 % variation of characteristic frequencies between bearing
#: manufacturers; the envelope peak search tolerance (2 %) covers this.
BEARING_6203 = BearingGeometry.from_preset("6203")


@dataclass(frozen=True)
class FileInfo:
    path: Path
    stem: str
    condition: OperatingCondition
    bearing: BearingInfo
    measurement_index: int


@dataclass(frozen=True)
class PaderbornMeasurement:
    x: FloatArray
    fs: float
    provenance: dict[str, Any]
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- names


def parse_filename(path: str | Path) -> FileInfo:
    """Parse ``N15_M07_F10_KA01_1.mat`` into operating condition, bearing and index."""
    p = Path(path)
    if p.suffix.lower() != ".mat":
        raise PaderbornFormatError(f"{p.name}: expected a .mat file")
    match = _FILENAME_RE.match(p.stem)
    if not match:
        raise PaderbornFormatError(
            f"{p.name}: name does not match '<N..>_<M..>_<F..>_<bearing>_<index>.mat', "
            "e.g. N15_M07_F10_KA01_1.mat"
        )
    code, bearing = match["condition"], match["bearing"]
    if code not in OPERATING_CONDITIONS:
        raise PaderbornFormatError(
            f"{p.name}: unknown operating condition {code!r}; known: {sorted(OPERATING_CONDITIONS)}"
        )
    if bearing not in BEARINGS:
        raise PaderbornFormatError(f"{p.name}: unknown bearing code {bearing!r}")
    return FileInfo(p, p.stem, OPERATING_CONDITIONS[code], BEARINGS[bearing], int(match["index"]))


# ---------------------------------------------------------------- .mat files


def _load_mat(path: Path) -> dict[str, Any]:
    try:
        mat: dict[str, Any] = sio.loadmat(str(path), simplify_cells=True)
    except NotImplementedError as exc:  # scipy raises this for MATLAB v7.3 (HDF5)
        raise PaderbornFileError(
            f"{path.name}: MATLAB v7.3/HDF5 files are not supported by scipy ({exc})"
        ) from exc
    except FileNotFoundError:
        raise
    except Exception as exc:  # corrupt or truncated files raise many exception types
        raise PaderbornFileError(
            f"{path.name}: cannot be read ({type(exc).__name__}: {exc})"
        ) from exc
    return mat


def _iter_channels(obj: Any, depth: int = 0) -> Iterator[dict[str, Any]]:
    """Yield every dict that looks like a channel record (has str Name and Data)."""
    if depth > 8:
        return
    if isinstance(obj, dict):
        if isinstance(obj.get("Name"), str) and "Data" in obj:
            yield obj
        for value in obj.values():
            yield from _iter_channels(value, depth + 1)
    elif isinstance(obj, list | tuple):
        for item in obj:
            yield from _iter_channels(item, depth + 1)
    elif isinstance(obj, np.ndarray) and obj.dtype == object:
        for item in obj.ravel():
            yield from _iter_channels(item, depth + 1)


def _text(value: Any) -> str:
    """A struct field as text. MATLAB stores empty fields as ``[]`` (an empty array).

    The real Paderborn files leave ``Unit`` empty for every channel, so
    ``str(value)`` or ``value or default`` would give ``"[]"`` or raise.
    """
    if value is None:
        return ""
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.size == 1:
            return str(value.item())
    return str(value)


def _channels(path: Path) -> dict[str, dict[str, Any]]:
    mat = _load_mat(path)
    payload = {k: v for k, v in mat.items() if not k.startswith("__")}
    root: Any = payload.get(path.stem, payload)
    found: dict[str, dict[str, Any]] = {}
    for ch in _iter_channels(root):
        found.setdefault(ch["Name"], ch)
    if not found:
        raise PaderbornFormatError(
            f"{path.name}: no channel records (fields 'Name' and 'Data') found; "
            f"top-level variables: {sorted(payload)}"
        )
    return found


def inspect_file(path: str | Path) -> list[dict[str, Any]]:
    """Describe every channel in a file: name, unit, raster, sample count."""
    p = Path(path)
    rows = []
    for name, ch in sorted(_channels(p).items()):
        data = np.asarray(ch.get("Data"))
        rows.append(
            {
                "name": name,
                "unit": _text(ch.get("Unit")),
                "raster": _text(ch.get("Raster")),
                "n_samples": int(data.size),
                "documented_fs_hz": CHANNEL_RATES_HZ.get(name),
            }
        )
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_measurement(
    path: str | Path,
    channel: str = "vibration_1",
    *,
    root: str | Path | None = None,
    expected_duration_s: float | None = NOMINAL_DURATION_S,
    duration_tolerance: float = 0.1,
    use_measured_speed: bool = True,
    compute_sha256: bool = False,
) -> PaderbornMeasurement:
    """Read one channel of one measurement, with a validated provenance record.

    Raises :class:`PaderbornFileError` for unreadable files and
    :class:`PaderbornFormatError` for unexpected names, channels or durations.

    Shaft speed: if a ``speed`` channel exists and its median lies within +/-20 % of
    the nominal setting, that measured value is used (``rpm_source=
    "measured_speed_channel"``); otherwise the nominal setting is used and a note
    explains why.
    """
    info = parse_filename(path)
    p = info.path
    channels = _channels(p)
    if channel not in channels:
        raise PaderbornFormatError(
            f"{p.name}: channel {channel!r} not found; available: {sorted(channels)}"
        )
    if channel not in CHANNEL_RATES_HZ:
        raise PaderbornFormatError(f"no documented sampling rate for channel {channel!r}")
    fs = CHANNEL_RATES_HZ[channel]
    x = np.asarray(channels[channel]["Data"], dtype=np.float64).ravel()
    if x.size < 2 or not np.all(np.isfinite(x)):
        raise PaderbornFormatError(f"{p.name}: channel {channel!r} is empty or non-finite")
    duration = x.size / fs
    if expected_duration_s is not None and (
        abs(duration - expected_duration_s) > duration_tolerance * expected_duration_s
    ):
        raise PaderbornFormatError(
            f"{p.name}: {x.size} samples = {duration:.3f} s at the documented {fs:g} Hz, "
            f"expected about {expected_duration_s:g} s (truncated file or wrong rate?)"
        )

    notes: list[str] = []
    rpm, rpm_source = info.condition.rpm, "nominal_setting"
    if use_measured_speed:
        speed = channels.get("speed")
        if speed is None:
            notes.append("no 'speed' channel; nominal speed used")
        else:
            values = np.asarray(speed["Data"], dtype=np.float64).ravel()
            values = values[np.isfinite(values)]
            median = float(np.median(values)) if values.size else math.nan
            if math.isfinite(median) and 0.8 * rpm <= median <= 1.2 * rpm:
                rpm, rpm_source = median, "measured_speed_channel"
            else:
                notes.append(
                    f"speed channel median {median:.4g} {_text(speed.get('Unit'))} not within "
                    f"+/-20 % of nominal {info.condition.rpm:g} rpm; nominal used"
                )

    rel = str(p.relative_to(root)) if root is not None else p.name
    sensor, location = _SENSORS.get(
        channel, ("see dataset documentation", "see dataset documentation")
    )
    record = {
        "dataset_id": DATASET_ID,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "citation": CITATION,
        "synthetic": False,
        "source_file": rel,
        "acquisition_id": info.stem,
        "group_id": info.bearing.code,
        "machine_type": MACHINE_TYPE,
        "sensor": sensor,
        "sensor_location": location,
        "channel": channel,
        "unit": _text(channels[channel].get("Unit")) or "unspecified in source",
        "calibration": "values as stored in the source file; no conversion applied",
        "fs_hz": fs,
        "duration_s": duration,
        "rpm": float(rpm),
        "rpm_source": rpm_source,
        "operating_condition": info.condition.code,
        "label": info.bearing.label,
        "label_method": (
            "bearing code per dataset publication: "
            + {
                "none": "undamaged reference bearing",
                "artificial": f"artificial damage ({info.bearing.damage})",
                "real": f"real damage from accelerated lifetime test ({info.bearing.damage})",
            }[info.bearing.damage_origin]
        ),
        "damage_origin": info.bearing.damage_origin,
    }
    if compute_sha256:
        record["sha256"] = _sha256(p)
    try:
        validated = validate_provenance(record, allowed_labels=LABELS)
    except ProvenanceError as exc:  # pragma: no cover - guards future edits of this module
        raise PaderbornFormatError(str(exc)) from exc
    return PaderbornMeasurement(x=x, fs=fs, provenance=validated, notes=notes)


# ------------------------------------------------------------------ scanning


def scan(root: str | Path) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Index every Paderborn ``.mat`` file under ``root`` (recursively) without loading it.

    Returns ``(index, skipped)``: one row per recognised file, and a list of
    ``{"file", "reason"}`` for ``.mat`` files whose names were not recognised.
    """
    base = Path(root)
    if not base.is_dir():
        raise FileNotFoundError(f"dataset folder not found: {base}")
    rows, skipped = [], []
    for path in sorted(base.rglob("*.mat")):
        try:
            info = parse_filename(path)
        except PaderbornFormatError as exc:
            skipped.append({"file": str(path.relative_to(base)), "reason": str(exc)})
            continue
        rows.append(
            {
                "path": str(path),
                "source_file": str(path.relative_to(base)),
                "acquisition_id": info.stem,
                "bearing": info.bearing.code,
                "label": info.bearing.label,
                "damage_origin": info.bearing.damage_origin,
                "operating_condition": info.condition.code,
                "measurement_index": info.measurement_index,
            }
        )
    columns = [
        "path", "source_file", "acquisition_id", "bearing", "label",
        "damage_origin", "operating_condition", "measurement_index",
    ]  # fmt: skip
    return pd.DataFrame(rows, columns=columns), skipped


def build_feature_table(
    root: str | Path,
    *,
    task: str = "real3",
    channel: str = "vibration_1",
    segment_seconds: float = 1.0,
    conditions: Iterable[str] | None = None,
    max_measurements: int | None = None,
    envelope_band: tuple[float, float] | None = None,
    expected_duration_s: float | None = NOMINAL_DURATION_S,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Segment every selected recording and extract transparent features.

    One row per non-overlapping segment. ``group_id`` is the **physical bearing**
    code, because all measurements of one bearing share its individual damage and
    mounting; splitting by recording would still leak bearing identity.

    Unreadable or malformed files are skipped and listed in the returned report
    instead of aborting the whole run.
    """
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; choose from {sorted(TASKS)}")
    if segment_seconds <= 0:
        raise ValueError("segment_seconds must be > 0")
    spec = TASKS[task]
    wanted_conditions = set(conditions) if conditions is not None else set(OPERATING_CONDITIONS)
    unknown = wanted_conditions - set(OPERATING_CONDITIONS)
    if unknown:
        raise ValueError(f"unknown operating condition(s) {sorted(unknown)}")

    index, skipped = scan(root)
    selected = index[
        index["bearing"].isin(spec.bearings) & index["operating_condition"].isin(wanted_conditions)
    ]
    if max_measurements is not None:
        selected = selected[selected["measurement_index"] <= max_measurements]

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    notes: dict[str, list[str]] = {}
    total = len(selected)
    for i, item in enumerate(selected.itertuples(index=False), start=1):
        if progress is not None:
            progress(i, total, item.source_file)
        try:
            meas = read_measurement(
                item.path, channel, root=root, expected_duration_s=expected_duration_s
            )
        except PaderbornError as exc:
            failures.append({"file": item.source_file, "error": str(exc)})
            continue
        if meas.notes:
            notes[item.source_file] = meas.notes
        prov = meas.provenance
        oc = OPERATING_CONDITIONS[prov["operating_condition"]]
        seg_len = int(round(segment_seconds * meas.fs))
        n_seg = meas.x.size // seg_len
        for k in range(n_seg):
            seg = meas.x[k * seg_len : (k + 1) * seg_len]
            feats = extract_all_features(
                seg, meas.fs, rpm=prov["rpm"], bearing=BEARING_6203, envelope_band=envelope_band
            )
            row: dict[str, Any] = {
                "sample_id": f"{prov['acquisition_id']}-s{k:02d}",
                "group_id": prov["group_id"],
                "acquisition_id": prov["acquisition_id"],
                "segment_index": k,
                "label": prov["label"],
                "damage_origin": prov["damage_origin"],
                "operating_condition": oc.code,
                "rpm": prov["rpm"],
                "rpm_source": prov["rpm_source"],
                "load_torque_nm": oc.load_torque_nm,
                "radial_force_n": oc.radial_force_n,
                "fs_hz": meas.fs,
                "unit": prov["unit"],
                "source_file": prov["source_file"],
                "dataset_id": DATASET_ID,
                "synthetic": False,
            }
            if spec.split is not None:
                row["split"] = spec.split[prov["group_id"]]
            row.update(feats)
            rows.append(row)

    missing_bearings = sorted(spec.bearings - set(index["bearing"]))
    from .paderborn_archives import load_verification

    verification = load_verification(root)
    report: dict[str, Any] = {
        "dataset_id": DATASET_ID,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "citation": CITATION,
        "machine_type": MACHINE_TYPE,
        "task": spec.name,
        "task_description": spec.description,
        "channel": channel,
        "segment_seconds": segment_seconds,
        "envelope_band_hz": list(envelope_band) if envelope_band else "default (0.1 fs, 0.4 fs)",
        "bearing_geometry": {
            "designation": "6203",
            "n_elements": BEARING_6203.n_elements,
            "ball_diameter_mm": BEARING_6203.ball_diameter_mm,
            "pitch_diameter_mm": BEARING_6203.pitch_diameter_mm,
            "note": "manufacturer-dependent; defect frequencies vary by about 1-2 %",
        },
        "conditions": sorted(wanted_conditions),
        "max_measurements": max_measurements,
        "n_files_found": int(len(index)),
        "n_files_selected": int(total),
        "n_files_used": int(total - len(failures)),
        "n_segments": len(rows),
        "missing_bearings": missing_bearings,
        "failures": failures,
        "skipped_files": skipped,
        "speed_notes": notes,
        "archive_verification": (
            {
                "source": verification.get("source"),
                "mirror": verification.get("mirror"),
                "archives_ok": verification.get("archives_ok"),
                "inventory_complete": verification.get("inventory_complete"),
                "checked_with_pumpguard": verification.get("pumpguard_version"),
            }
            if verification
            else "not verified: run `pumpguard paderborn verify` on this folder first"
        ),
        "pumpguard_version": __version__,
    }
    if not rows:
        raise PaderbornError(
            f"no usable recordings for task {task!r} under {root}. Expected files such as "
            f"K001/N15_M07_F10_K001_1.mat. Found {len(index)} recognised file(s); "
            f"{len(failures)} failed. Missing bearings: {missing_bearings}"
        )
    return pd.DataFrame(rows), report
