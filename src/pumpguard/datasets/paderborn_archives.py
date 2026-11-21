"""Integrity checks for Paderborn KAt archives and extracted files.

Two checks, both run before any feature is computed:

1. **Archives** (:func:`verify_archives`): each ``.rar`` has the size and MD5
   published by its source. The built-in manifest is the Zenodo mirror
   (DOI 10.5281/zenodo.15845309, read from the Zenodo files API on 2026-11-21).
2. **Inventory** (:func:`check_inventory`): after extraction, every selected
   bearing has 20 measurements in each of the 4 operating conditions, with no
   duplicates and no gaps in the measurement numbers.

About the mirror: it was uploaded by a third party (J. van den Hoogen, Osnabrück
University), has no description and labels itself CC BY 4.0. A copy cannot
relax the original licence, so the files remain **CC BY-NC 4.0** and must be
cited as Lessmeier et al. (2016). The MD5s prove the files match the mirror,
not that the mirror matches the university's originals. Bearing KA08 is not in
the mirror.

:func:`write_verification` stores the result as ``paderborn_verification.json``
in the data folder; :func:`~pumpguard.datasets.paderborn.build_feature_table`
copies it into its report, so every feature table records how its source files
were checked.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._version import __version__
from .paderborn import BEARINGS, OPERATING_CONDITIONS, TASKS, scan

__all__ = [
    "MEASUREMENTS_PER_CONDITION",
    "VERIFICATION_FILE",
    "ZENODO_DOI",
    "ZENODO_MANIFEST",
    "ZENODO_URL",
    "ArchiveSpec",
    "check_inventory",
    "load_verification",
    "md5sum",
    "verify_archives",
    "write_verification",
]

ZENODO_DOI = "10.5281/zenodo.15845309"
ZENODO_URL = "https://zenodo.org/records/15845309"
VERIFICATION_FILE = "paderborn_verification.json"
MEASUREMENTS_PER_CONDITION = 20


@dataclass(frozen=True)
class ArchiveSpec:
    name: str
    bytes: int
    md5: str

    @property
    def bearing(self) -> str:
        return self.name.removesuffix(".rar")

    @property
    def url(self) -> str:
        return f"{ZENODO_URL}/files/{self.name}?download=1"


def _spec(line: str) -> ArchiveSpec:
    name, size, md5 = line.split(",")
    return ArchiveSpec(name, int(size), md5)


#: Every archive in the Zenodo mirror: name, size in bytes, MD5 (Zenodo files API).
ZENODO_MANIFEST: dict[str, ArchiveSpec] = {
    s.bearing: s
    for s in map(
        _spec,
        """\
K001.rar,173881721,af6dc58283d356cd438e7738a2d525b8
K002.rar,161981588,88631bc0081a6470846d18189d46381d
K003.rar,173194389,08b61792e1058dc47dd21071666bca2c
K004.rar,163337851,5b9fde1c6d754806539f9a890ee6bbdd
K005.rar,167366765,28d91412ad14583fbdfda958b64a8267
K006.rar,175997605,b36389294fc5a21539d9fcfacfa3604a
KA01.rar,166571438,5627ec9320199078205db5325c1c2f84
KA03.rar,176196084,0bba6927ac1732d23934a909af4c1fc6
KA04.rar,180920703,f87503ed69a624ba6e1d9e573e6c09fb
KA05.rar,163644977,22b6ffd9ff083f084918c34f6ddcc538
KA06.rar,164139086,be58a820fee4851b2c16a97a88c282cb
KA07.rar,160346192,185e3de688149ebabf20c51d80fd7dd8
KA09.rar,171467156,de9392fdbf878171a429c2451d2696fd
KA15.rar,164268273,db518f97ba5bcaedb09c648a317431e0
KA16.rar,167165704,ef848f5621f9c10523c313131d1a4c21
KA22.rar,159054470,7a16a5bc88d5fe1d83d169f88f0709e8
KA30.rar,163625195,715c0cf7862a7ba83e7c6a6fb5c91a61
KB23.rar,170933916,bb87c72669baa9dbbefd10b5294ffcc8
KB24.rar,186677308,c60ce8867c824583540794ae00cce333
KB27.rar,162452979,965dd4af26391d7def4638c8b31a87e7
KI01.rar,175265779,03429a4ab5e3768b7395d1654e55bead
KI03.rar,159217524,26f0452f00ab698a4e657e27b7a249b3
KI04.rar,172644279,a5a634fcdcb33a8501e7411d30441c6d
KI05.rar,160359281,c777459ddc7a1d38df7155f09e0ce782
KI07.rar,160646876,c26144f53ebcc34562bdc2e3a0ef1087
KI08.rar,163760131,f546b3481ffdcd80f0d14a797db48deb
KI14.rar,163581312,13603834975435ca10eb08de6d1840dc
KI16.rar,166348305,db14eae04a213afd0d1ca99d3d850342
KI17.rar,167363476,d1055fe5cc44948e5d3a39f2e0db9dbe
KI18.rar,161226797,db5da511e9240dbc56ec1e850fd91699
KI21.rar,164882839,911ce3e37a86d258818e3e93274752a2""".splitlines(),
    )
}


def md5sum(path: str | Path, block: int = 1 << 20) -> str:
    """MD5 of a file, read in 1 MiB blocks (archives are ~170 MB)."""
    digest = hashlib.md5(usedforsecurity=False)
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(block), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bearings_for(task: str | None, bearings: Iterable[str] | None) -> list[str]:
    if bearings is not None:
        chosen = sorted(set(bearings))
    elif task is not None:
        if task not in TASKS:
            raise ValueError(f"unknown task {task!r}; choose from {sorted(TASKS)}")
        chosen = sorted(TASKS[task].bearings)
    else:
        chosen = sorted(BEARINGS)
    unknown = [b for b in chosen if b not in BEARINGS]
    if unknown:
        raise ValueError(f"unknown bearing code(s) {unknown}")
    return chosen


def verify_archives(
    folder: str | Path,
    *,
    task: str | None = "real3",
    bearings: Iterable[str] | None = None,
    manifest: dict[str, ArchiveSpec] = ZENODO_MANIFEST,
) -> list[dict[str, Any]]:
    """Check size and MD5 of each expected ``<bearing>.rar`` in ``folder``.

    One row per bearing with ``status`` in ``ok``, ``missing``, ``size_mismatch``,
    ``md5_mismatch`` or ``not_in_manifest`` (e.g. KA08, absent from the mirror).
    The MD5 is computed only when the size already matches.
    """
    base = Path(folder)
    if not base.is_dir():
        raise FileNotFoundError(f"archive folder not found: {base}")
    rows = []
    for code in _bearings_for(task, bearings):
        spec = manifest.get(code)
        row: dict[str, Any] = {"bearing": code, "file": f"{code}.rar"}
        path = base / f"{code}.rar"
        if spec is None:
            row["status"] = "not_in_manifest"
        elif not path.is_file():
            row["status"] = "missing"
        else:
            size = path.stat().st_size
            row.update(expected_bytes=spec.bytes, bytes=size, expected_md5=spec.md5)
            if size != spec.bytes:
                row["status"] = "size_mismatch"
            else:
                row["md5"] = md5sum(path)
                row["status"] = "ok" if row["md5"] == spec.md5 else "md5_mismatch"
        rows.append(row)
    return rows


def check_inventory(
    root: str | Path,
    *,
    task: str | None = "real3",
    bearings: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Count extracted measurements per bearing and operating condition.

    Expected: indices 1..20 in each of the 4 conditions. Reports missing
    indices, duplicates (the same file name in two folders) and extra indices.
    """
    index, skipped = scan(root)
    chosen = _bearings_for(task, bearings)
    expected = set(range(1, MEASUREMENTS_PER_CONDITION + 1))
    per_bearing: dict[str, Any] = {}
    for code in chosen:
        sub = index[index["bearing"] == code]
        conditions: dict[str, Any] = {}
        for oc in sorted(OPERATING_CONDITIONS):
            got = sub.loc[sub["operating_condition"] == oc, "measurement_index"].tolist()
            seen = set(got)
            conditions[oc] = {
                "n_files": len(got),
                "missing_indices": sorted(expected - seen),
                "extra_indices": sorted(seen - expected),
                "duplicates": sorted({i for i in got if got.count(i) > 1}),
            }
        complete = all(
            c["n_files"] == MEASUREMENTS_PER_CONDITION
            and not (c["missing_indices"] or c["extra_indices"] or c["duplicates"])
            for c in conditions.values()
        )
        per_bearing[code] = {"complete": complete, "n_files": len(sub), "conditions": conditions}
    return {
        "expected_per_bearing": MEASUREMENTS_PER_CONDITION * len(OPERATING_CONDITIONS),
        "bearings": per_bearing,
        "complete": all(b["complete"] for b in per_bearing.values()),
        "n_unrecognised_mat_files": len(skipped),
    }


def write_verification(
    root: str | Path,
    archives: list[dict[str, Any]] | None,
    inventory: dict[str, Any],
    *,
    source: str = "zenodo",
) -> Path:
    """Write ``paderborn_verification.json`` into ``root`` and return its path."""
    payload: dict[str, Any] = {
        "pumpguard_version": __version__,
        "source": source,
        "license_of_original_data": "CC BY-NC 4.0",
        "inventory_complete": inventory["complete"],
        "inventory": inventory,
    }
    if source == "zenodo":
        payload["mirror"] = {
            "doi": ZENODO_DOI,
            "url": ZENODO_URL,
            "uploader": "J. van den Hoogen (Osnabrück University)",
            "license_label_on_mirror": "CC BY 4.0 (cannot relax the original CC BY-NC 4.0)",
            "missing_from_mirror": sorted(set(BEARINGS) - set(ZENODO_MANIFEST)),
        }
    if archives is not None:
        payload["archives"] = archives
        payload["archives_ok"] = all(a["status"] == "ok" for a in archives)
    path = Path(root) / VERIFICATION_FILE
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_verification(root: str | Path) -> dict[str, Any] | None:
    """Return the stored verification of ``root``, or ``None`` if there is none."""
    path = Path(root) / VERIFICATION_FILE
    if not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
