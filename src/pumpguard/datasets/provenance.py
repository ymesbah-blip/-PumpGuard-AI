"""Provenance schema for every recording or segment that enters an analysis.

A result is only as trustworthy as what is known about its data. This module
defines the minimum record that must accompany each measured (or synthetic)
recording, and validates it with explicit, collected error messages.

The schema follows ``docs/datasets.md``: source and licence, physical units and
calibration status, sampling rate and duration, how speed was obtained, the
operating point, how the label was produced, and the acquisition group used
for leakage-safe splitting.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

__all__ = [
    "ALLOWED_DAMAGE_ORIGINS",
    "ALLOWED_RPM_SOURCES",
    "REQUIRED_FIELDS",
    "ProvenanceError",
    "validate_provenance",
]


class ProvenanceError(ValueError):
    """Raised when a provenance record is incomplete or inconsistent.

    ``problems`` lists every issue found, not only the first one.
    """

    def __init__(self, problems: list[str], record_id: str = "record") -> None:
        self.problems = problems
        bullet = "\n  - "
        super().__init__(f"invalid provenance for {record_id}:{bullet}{bullet.join(problems)}")


#: Field name -> (expected type(s), description). Every field is mandatory.
REQUIRED_FIELDS: dict[str, tuple[type | tuple[type, ...], str]] = {
    "dataset_id": (str, "short identifier of the dataset, e.g. 'paderborn-kat'"),
    "source_url": (str, "where the original data can be obtained"),
    "license": (str, "licence of the original data, e.g. 'CC BY-NC 4.0'"),
    "citation": (str, "required citation of the original data"),
    "synthetic": (bool, "True only for generated signals"),
    "source_file": (str, "file name or relative path of the original recording"),
    "acquisition_id": (str, "identifier of one acquisition (one recording)"),
    "group_id": (str, "unit that must never be split across train/test (machine, bearing)"),
    "machine_type": (str, "what was measured, e.g. 'bearing test rig'"),
    "sensor": (str, "sensor type/model"),
    "sensor_location": (str, "mounting location and direction"),
    "channel": (str, "channel name in the source file"),
    "unit": (str, "physical unit of the stored values, as stated by the source"),
    "calibration": (str, "calibration status / conversion applied (or 'none applied')"),
    "fs_hz": ((int, float), "sampling rate in Hz"),
    "duration_s": ((int, float), "duration in seconds"),
    "rpm": ((int, float), "shaft speed used for order/bearing features"),
    "rpm_source": (str, "how rpm was obtained, see ALLOWED_RPM_SOURCES"),
    "operating_condition": (str, "operating-point code or description"),
    "label": (str, "class label"),
    "label_method": (str, "how the label was established"),
    "damage_origin": (str, "see ALLOWED_DAMAGE_ORIGINS"),
}

ALLOWED_RPM_SOURCES: frozenset[str] = frozenset(
    {"measured_speed_channel", "nominal_setting", "tachometer", "user_supplied", "synthetic"}
)
ALLOWED_DAMAGE_ORIGINS: frozenset[str] = frozenset(
    {"none", "artificial", "real", "synthetic", "unknown"}
)


def validate_provenance(
    record: Mapping[str, Any], *, allowed_labels: frozenset[str] | None = None
) -> dict[str, Any]:
    """Check ``record`` against :data:`REQUIRED_FIELDS` and consistency rules.

    Returns a plain ``dict`` copy on success; raises :class:`ProvenanceError`
    listing every problem otherwise.
    """
    problems: list[str] = []
    for name, (expected, description) in REQUIRED_FIELDS.items():
        if name not in record or record[name] is None:
            problems.append(f"missing '{name}' ({description})")
            continue
        value = record[name]
        # bool is a subclass of int: reject it for numeric fields explicitly.
        numeric = expected == (int, float)
        if (numeric and isinstance(value, bool)) or not isinstance(value, expected):
            problems.append(f"'{name}' has type {type(value).__name__}, expected {expected}")
        elif isinstance(value, str) and not value.strip():
            problems.append(f"'{name}' is empty ({description})")

    def _number(name: str) -> float | None:
        value = record.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)

    for name in ("fs_hz", "duration_s", "rpm"):
        number = _number(name)
        if number is not None and (not math.isfinite(number) or number <= 0):
            problems.append(f"'{name}' must be a positive finite number, got {number!r}")

    rpm_source = record.get("rpm_source")
    if isinstance(rpm_source, str) and rpm_source not in ALLOWED_RPM_SOURCES:
        problems.append(f"'rpm_source'={rpm_source!r} not in {sorted(ALLOWED_RPM_SOURCES)}")
    origin = record.get("damage_origin")
    if isinstance(origin, str) and origin not in ALLOWED_DAMAGE_ORIGINS:
        problems.append(f"'damage_origin'={origin!r} not in {sorted(ALLOWED_DAMAGE_ORIGINS)}")
    label = record.get("label")
    if allowed_labels is not None and isinstance(label, str) and label not in allowed_labels:
        problems.append(f"'label'={label!r} not in {sorted(allowed_labels)}")

    synthetic = record.get("synthetic")
    if synthetic is True and (origin not in (None, "synthetic") or rpm_source != "synthetic"):
        problems.append("synthetic records must use damage_origin and rpm_source 'synthetic'")
    if synthetic is False and (origin == "synthetic" or rpm_source == "synthetic"):
        problems.append("a measured record (synthetic=False) cannot have synthetic origin/rpm")

    if problems:
        rid = str(record.get("acquisition_id") or record.get("source_file") or "record")
        raise ProvenanceError(problems, rid)
    return dict(record)
