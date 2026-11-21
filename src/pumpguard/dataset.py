"""Labelled synthetic feature tables and leakage-safe splitting.

Real condition-monitoring datasets usually contain many segments cut from the
same recording or machine. If segments from one machine land in both the
training and the test set, a model can memorise the machine instead of the
fault, and reported accuracy is inflated (data leakage).

:func:`make_synthetic_dataset` mimics that structure: each *virtual machine*
(``group_id``) has its own speed, noise level and fault severity, and
contributes several segments. :func:`group_train_test_split` keeps every group
entirely on one side of the split.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .features import extract_all_features
from .signals import CONDITIONS, SignalConfig, simulate

__all__ = ["group_train_test_split", "make_synthetic_dataset"]


def _check_range(name: str, rng: tuple[float, float], minimum: float = 0.0) -> None:
    low, high = rng
    if not (minimum <= low <= high):
        raise ValueError(f"{name} must satisfy {minimum:g} <= low <= high, got {rng}")


def make_synthetic_dataset(
    conditions: Sequence[str] = CONDITIONS,
    machines_per_condition: int = 4,
    segments_per_machine: int = 5,
    *,
    rpm_range: tuple[float, float] = (1450.0, 3000.0),
    noise_range: tuple[float, float] = (0.03, 0.10),
    severity_range: tuple[float, float] = (0.5, 1.5),
    fs: float = 12_000.0,
    duration: float = 1.0,
    n_vanes: int = 5,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a labelled feature table from synthetic recordings.

    One row per segment with columns ``sample_id``, ``group_id``, ``condition``,
    ``rpm``, ``noise_std``, ``severity``, ``seed``, ``synthetic`` (always ``True``)
    followed by every feature from :func:`~pumpguard.features.extract_all_features`.
    """
    unknown = sorted(set(conditions) - set(CONDITIONS))
    if unknown or not conditions:
        raise ValueError(f"conditions must be a non-empty subset of {list(CONDITIONS)}")
    if machines_per_condition < 1 or segments_per_machine < 1:
        raise ValueError("machines_per_condition and segments_per_machine must be >= 1")
    _check_range("rpm_range", rpm_range, minimum=1e-9)
    _check_range("noise_range", noise_range)
    _check_range("severity_range", severity_range)

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for condition in conditions:
        for m in range(machines_per_condition):
            group_id = f"{condition}-m{m:02d}"
            rpm_m = float(rng.uniform(*rpm_range))
            noise_m = float(rng.uniform(*noise_range))
            severity = 0.0 if condition == "healthy" else float(rng.uniform(*severity_range))
            for s in range(segments_per_machine):
                seg_seed = int(rng.integers(0, 2**31 - 1))
                rpm_s = rpm_m * (1.0 + 0.005 * float(rng.standard_normal()))  # speed drift
                cfg = SignalConfig(
                    condition=condition,
                    fs=fs,
                    duration=duration,
                    rpm=rpm_s,
                    seed=seg_seed,
                    noise_std=noise_m,
                    severity=severity,
                    n_vanes=n_vanes,
                )
                sig = simulate(cfg)
                feats = extract_all_features(
                    sig.x, fs, rpm=rpm_s, n_vanes=n_vanes, bearing=cfg.bearing
                )
                rows.append(
                    {
                        "sample_id": f"{group_id}-s{s:02d}",
                        "group_id": group_id,
                        "condition": condition,
                        "rpm": rpm_s,
                        "noise_std": noise_m,
                        "severity": severity,
                        "seed": seg_seed,
                        "synthetic": True,
                        **feats,
                    }
                )
    return pd.DataFrame(rows)


def group_train_test_split(
    df: pd.DataFrame,
    test_fraction: float = 0.25,
    *,
    group_col: str = "group_id",
    stratify_col: str | None = "condition",
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows so that no group appears in both train and test.

    With ``stratify_col`` set, groups are split separately within each stratum so
    every class is represented on both sides when it has at least two groups.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be in (0, 1)")
    if group_col not in df.columns:
        raise ValueError(f"missing group column {group_col!r}")

    if stratify_col is None:
        strata: dict[object, list[object]] = {None: sorted(df[group_col].unique())}
    else:
        if stratify_col not in df.columns:
            raise ValueError(f"missing stratify column {stratify_col!r}")
        if int(df.groupby(group_col)[stratify_col].nunique().max()) > 1:
            raise ValueError(f"each {group_col!r} must map to exactly one {stratify_col!r}")
        strata = {
            key: sorted(groups)
            for key, groups in df.groupby(stratify_col)[group_col].unique().items()
        }

    rng = np.random.default_rng(seed)
    test_groups: list[object] = []
    for key in sorted(strata, key=str):
        groups = list(strata[key])
        rng.shuffle(groups)
        n_test = max(1, round(len(groups) * test_fraction)) if len(groups) > 1 else 0
        test_groups.extend(groups[:n_test])

    is_test = df[group_col].isin(test_groups)
    return df[~is_test].reset_index(drop=True), df[is_test].reset_index(drop=True)
