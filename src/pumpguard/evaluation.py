"""Leakage-safe evaluation: group-aware folds, metrics and group-bootstrap intervals.

Why group-aware: segments cut from the same machine, bearing or recording share
properties unrelated to the fault (mounting, individual damage geometry,
sensor coupling). If they appear on both sides of a split, a model can
recognise the *unit* instead of the *condition*, and accuracy is inflated.
Every function here takes the group of each sample into account.

Why a group bootstrap: the number of independent units (e.g. 15 bearings) is
far smaller than the number of segments (thousands). Confidence intervals are
therefore computed by resampling groups, not segments.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "classification_metrics",
    "confusion_matrix",
    "group_bootstrap_ci",
    "random_kfold",
    "stratified_group_kfold",
]

Fold = tuple[NDArray[np.intp], NDArray[np.intp]]


def _as_labels(values: ArrayLike) -> NDArray[np.object_]:
    return np.asarray(values, dtype=object).ravel()


def confusion_matrix(
    y_true: ArrayLike, y_pred: ArrayLike, labels: Sequence[Any]
) -> NDArray[np.int64]:
    """Counts with rows = true label, columns = predicted label, in ``labels`` order."""
    t, p = _as_labels(y_true), _as_labels(y_pred)
    if t.size != p.size:
        raise ValueError("y_true and y_pred must have the same length")
    pos = {label: i for i, label in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for a, b in zip(t, p, strict=True):
        if a not in pos or b not in pos:
            raise ValueError(f"label {a if a not in pos else b!r} not in labels {list(labels)}")
        cm[pos[a], pos[b]] += 1
    return cm


def classification_metrics(
    y_true: ArrayLike, y_pred: ArrayLike, labels: Sequence[Any] | None = None
) -> dict[str, Any]:
    """Accuracy, balanced accuracy, macro-F1 and per-class precision/recall/F1.

    Precision of a class that is never predicted is reported as 0.0. Balanced
    accuracy is the mean recall over classes present in ``y_true``.
    """
    t, p = _as_labels(y_true), _as_labels(y_pred)
    if t.size == 0:
        raise ValueError("cannot compute metrics on zero samples")
    labs = list(labels) if labels is not None else sorted(set(t) | set(p), key=str)
    cm = confusion_matrix(t, p, labs)
    support = cm.sum(axis=1)
    predicted = cm.sum(axis=0)
    tp = np.diag(cm)
    per_class: dict[str, dict[str, float]] = {}
    recalls, f1s = [], []
    for i, label in enumerate(labs):
        precision = tp[i] / predicted[i] if predicted[i] else 0.0
        recall = tp[i] / support[i] if support[i] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[str(label)] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": int(support[i]),
        }
        if support[i]:
            recalls.append(recall)
            f1s.append(f1)
    return {
        "n": int(t.size),
        "accuracy": float(tp.sum() / t.size),
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "labels": [str(label) for label in labs],
        "confusion_matrix": cm.tolist(),
        "per_class": per_class,
    }


def stratified_group_kfold(
    groups: ArrayLike, labels: ArrayLike, n_splits: int = 5, seed: int = 0
) -> list[Fold]:
    """Folds in which every group is tested exactly once and never also trained on.

    Groups of each class are shuffled and dealt round-robin to folds, so classes
    are spread across folds as evenly as their group counts allow. Each group
    must have a single label.
    """
    g, y = _as_labels(groups), _as_labels(labels)
    if g.size != y.size:
        raise ValueError("groups and labels must have the same length")
    group_label: dict[Any, Any] = {}
    for gi, yi in zip(g, y, strict=True):
        if group_label.setdefault(gi, yi) != yi:
            raise ValueError(f"group {gi!r} has more than one label")
    unique_groups = sorted(group_label, key=str)
    if n_splits < 2 or n_splits > len(unique_groups):
        raise ValueError(f"n_splits must be in [2, {len(unique_groups)}] (number of groups)")

    rng = np.random.default_rng(seed)
    fold_of: dict[Any, int] = {}
    offset = 0
    for label in sorted(set(group_label.values()), key=str):
        members = [grp for grp in unique_groups if group_label[grp] == label]
        rng.shuffle(members)
        for j, grp in enumerate(members):
            fold_of[grp] = (offset + j) % n_splits
        offset += len(members)  # continue dealing where the previous class stopped

    fold_ids = np.array([fold_of[gi] for gi in g])
    folds: list[Fold] = []
    for k in range(n_splits):
        test = np.flatnonzero(fold_ids == k)
        if test.size == 0:
            continue
        folds.append((np.flatnonzero(fold_ids != k), test))
    return folds


def random_kfold(n_samples: int, n_splits: int = 5, seed: int = 0) -> list[Fold]:
    """Plain shuffled k-fold that **ignores groups**.

    Only for quantifying leakage: compare its scores with group k-fold.
    """
    if n_splits < 2 or n_splits > n_samples:
        raise ValueError(f"n_splits must be in [2, {n_samples}]")
    order = np.random.default_rng(seed).permutation(n_samples)
    return [
        (np.setdiff1d(order, part, assume_unique=True), np.sort(part))
        for part in np.array_split(order, n_splits)
    ]


def group_bootstrap_ci(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    groups: ArrayLike,
    metric: Callable[[NDArray[np.object_], NDArray[np.object_]], float],
    *,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile confidence interval of ``metric`` by resampling whole groups.

    Each bootstrap replicate draws as many groups as exist, with replacement, and
    pools all their samples. With few groups the interval is wide; that is the
    honest answer, not a defect.
    """
    t, p, g = _as_labels(y_true), _as_labels(y_pred), _as_labels(groups)
    if not (t.size == p.size == g.size) or t.size == 0:
        raise ValueError("y_true, y_pred and groups must be non-empty and equally long")
    if not 0 < alpha < 1 or n_boot < 1:
        raise ValueError("alpha must be in (0, 1) and n_boot >= 1")
    unique = sorted(set(g), key=str)
    members = [np.flatnonzero(g == grp) for grp in unique]
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, len(unique), size=len(unique))
        idx = np.concatenate([members[i] for i in pick])
        stats[b] = metric(t[idx], p[idx])
    low, high = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)
