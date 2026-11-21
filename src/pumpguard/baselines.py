"""Transparent, non-ML baselines.

Any learned classifier reported in this project must be compared against these
first. Each baseline can explain its decision in one sentence
(:meth:`describe`), and everything is fitted on training data only.

* :class:`MajorityClass`: always predicts the most frequent training class.
* :class:`SingleFeatureThreshold`: healthy vs damaged from the single best
  feature and threshold.
* :class:`EnvelopeRule`: physics rule. "Damaged" if an envelope peak at BPFO or
  BPFI is prominent; outer vs inner by which peak is larger.
* :class:`NearestCentroid`: nearest class mean in standardised feature space.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

__all__ = ["EnvelopeRule", "MajorityClass", "NearestCentroid", "SingleFeatureThreshold"]

_MAX_CANDIDATES = 512


def _labels(y: ArrayLike) -> NDArray[np.object_]:
    return np.asarray(y, dtype=object).ravel()


def _matrix(X: pd.DataFrame, columns: Sequence[str]) -> NDArray[np.float64]:
    missing = [c for c in columns if c not in X.columns]
    if missing:
        raise ValueError(f"missing feature column(s): {missing}")
    values: NDArray[np.float64] = np.asarray(X[list(columns)].to_numpy(), dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"non-finite values in feature column(s) {list(columns)}")
    return values


def best_threshold(values: ArrayLike, positive: ArrayLike) -> tuple[float, int, float]:
    """Threshold and direction maximising balanced accuracy for a binary split.

    Returns ``(threshold, direction, balanced_accuracy)``; ``direction=+1`` means
    "positive if value > threshold", ``-1`` means "positive if value < threshold".
    """
    v = np.asarray(values, dtype=np.float64).ravel()
    pos = np.asarray(positive, dtype=bool).ravel()
    if v.size != pos.size or v.size == 0:
        raise ValueError("values and positive must be non-empty and equally long")
    if pos.all() or not pos.any():
        raise ValueError("both classes are needed to fit a threshold")
    sp, sn = np.sort(v[pos]), np.sort(v[~pos])
    uniq = np.unique(v)
    mids = (uniq[:-1] + uniq[1:]) / 2 if uniq.size > 1 else uniq
    if mids.size > _MAX_CANDIDATES:
        mids = np.unique(np.quantile(mids, np.linspace(0, 1, _MAX_CANDIDATES)))
    candidates = np.concatenate(([uniq[0] - 1.0], mids, [uniq[-1] + 1.0]))
    # direction +1: positive if v > t
    tpr_up = (sp.size - np.searchsorted(sp, candidates, side="right")) / sp.size
    tnr_up = np.searchsorted(sn, candidates, side="right") / sn.size
    # direction -1: positive if v < t
    tpr_dn = np.searchsorted(sp, candidates, side="left") / sp.size
    tnr_dn = (sn.size - np.searchsorted(sn, candidates, side="left")) / sn.size
    bal_up, bal_dn = (tpr_up + tnr_up) / 2, (tpr_dn + tnr_dn) / 2
    i_up, i_dn = int(np.argmax(bal_up)), int(np.argmax(bal_dn))
    if bal_up[i_up] >= bal_dn[i_dn]:
        return float(candidates[i_up]), 1, float(bal_up[i_up])
    return float(candidates[i_dn]), -1, float(bal_dn[i_dn])


class MajorityClass:
    name = "majority_class"

    def __init__(self) -> None:
        self.label_: Any = None

    def fit(self, X: pd.DataFrame, y: ArrayLike) -> MajorityClass:
        counts = Counter(_labels(y))
        if not counts:
            raise ValueError("cannot fit on zero samples")
        self.label_ = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]
        return self

    def predict(self, X: pd.DataFrame) -> NDArray[np.object_]:
        return np.full(len(X), self.label_, dtype=object)

    def describe(self) -> str:
        return f"always predicts '{self.label_}'"


class SingleFeatureThreshold:
    """Binary detector: chooses one feature, threshold and direction on training data."""

    name = "single_feature_threshold"

    def __init__(
        self,
        features: Sequence[str],
        negative_label: str = "healthy",
        positive_label: str = "damaged",
    ) -> None:
        if not features:
            raise ValueError("at least one feature is required")
        self.features = list(features)
        self.negative_label = negative_label
        self.positive_label = positive_label
        self.feature_: str | None = None
        self.threshold_ = float("nan")
        self.direction_ = 1
        self.train_score_ = float("nan")

    def fit(self, X: pd.DataFrame, y: ArrayLike) -> SingleFeatureThreshold:
        labels = _labels(y)
        allowed = {self.negative_label, self.positive_label}
        if not set(labels) <= allowed:
            raise ValueError(
                f"labels must be {sorted(allowed)}, got {sorted(set(labels), key=str)}"
            )
        positive = labels == self.positive_label
        values = _matrix(X, self.features)
        best: tuple[float, str, float, int] | None = None
        for j, feature in enumerate(self.features):
            t, d, score = best_threshold(values[:, j], positive)
            if best is None or score > best[0]:
                best = (score, feature, t, d)
        assert best is not None
        self.train_score_, self.feature_, self.threshold_, self.direction_ = best
        return self

    def predict(self, X: pd.DataFrame) -> NDArray[np.object_]:
        if self.feature_ is None:
            raise RuntimeError("fit() must be called before predict()")
        v = _matrix(X, [self.feature_])[:, 0]
        hit = v > self.threshold_ if self.direction_ > 0 else v < self.threshold_
        return np.where(hit, self.positive_label, self.negative_label).astype(object)

    def describe(self) -> str:
        op = ">" if self.direction_ > 0 else "<"
        return f"'{self.positive_label}' if {self.feature_} {op} {self.threshold_:.4g}"


class EnvelopeRule:
    """Physics rule on envelope-spectrum peak ratios at BPFO and BPFI.

    One parameter is fitted: the threshold on ``max(bpfo_ratio, bpfi_ratio)``
    separating healthy from damaged (maximum balanced accuracy on training data).
    Outer vs inner is decided by which ratio is larger, with no fitting.
    ``mode="detection"`` returns only healthy/damaged.
    """

    name = "envelope_rule"

    def __init__(
        self,
        mode: str = "diagnosis",
        *,
        healthy_label: str = "healthy",
        outer_label: str = "outer",
        inner_label: str = "inner",
        damaged_label: str = "damaged",
        bpfo_col: str = "env_bpfo_ratio",
        bpfi_col: str = "env_bpfi_ratio",
    ) -> None:
        if mode not in ("diagnosis", "detection"):
            raise ValueError("mode must be 'diagnosis' or 'detection'")
        self.mode = mode
        self.healthy_label, self.outer_label = healthy_label, outer_label
        self.inner_label, self.damaged_label = inner_label, damaged_label
        self.columns = [bpfo_col, bpfi_col]
        self.threshold_ = float("nan")

    @property
    def labels(self) -> set[str]:
        if self.mode == "detection":
            return {self.healthy_label, self.damaged_label}
        return {self.healthy_label, self.outer_label, self.inner_label}

    def fit(self, X: pd.DataFrame, y: ArrayLike) -> EnvelopeRule:
        labels = _labels(y)
        if not set(labels) <= self.labels:
            raise ValueError(f"labels must be a subset of {sorted(self.labels)}")
        score = _matrix(X, self.columns).max(axis=1)
        t, direction, _ = best_threshold(score, labels != self.healthy_label)
        # A prominent peak must indicate damage; never accept the inverted rule.
        self.threshold_ = t if direction > 0 else float(np.max(score)) + 1.0
        return self

    def predict(self, X: pd.DataFrame) -> NDArray[np.object_]:
        if not np.isfinite(self.threshold_):
            raise RuntimeError("fit() must be called before predict()")
        m = _matrix(X, self.columns)
        damaged = m.max(axis=1) > self.threshold_
        if self.mode == "detection":
            return np.where(damaged, self.damaged_label, self.healthy_label).astype(object)
        kind = np.where(m[:, 0] >= m[:, 1], self.outer_label, self.inner_label)
        return np.where(damaged, kind, self.healthy_label).astype(object)

    def describe(self) -> str:
        rule = f"damaged if max(BPFO, BPFI envelope ratio) > {self.threshold_:.3g}"
        return rule if self.mode == "detection" else rule + "; outer if BPFO ratio >= BPFI ratio"


class NearestCentroid:
    """Nearest class mean after z-scoring with training statistics."""

    name = "nearest_centroid"

    def __init__(self, features: Sequence[str]) -> None:
        if not features:
            raise ValueError("at least one feature is required")
        self.features = list(features)
        self.mean_: NDArray[np.float64] | None = None
        self.scale_: NDArray[np.float64] | None = None
        self.classes_: list[Any] = []
        self.centroids_: NDArray[np.float64] | None = None

    def fit(self, X: pd.DataFrame, y: ArrayLike) -> NearestCentroid:
        labels = _labels(y)
        values = _matrix(X, self.features)
        if values.shape[0] != labels.size or labels.size == 0:
            raise ValueError("X and y must be non-empty and equally long")
        self.mean_ = values.mean(axis=0)
        scale = values.std(axis=0)
        self.scale_ = np.where(scale > 0, scale, 1.0)
        z = (values - self.mean_) / self.scale_
        self.classes_ = sorted(set(labels), key=str)
        self.centroids_ = np.vstack([z[labels == c].mean(axis=0) for c in self.classes_])
        return self

    def predict(self, X: pd.DataFrame) -> NDArray[np.object_]:
        if self.centroids_ is None or self.mean_ is None or self.scale_ is None:
            raise RuntimeError("fit() must be called before predict()")
        z = (_matrix(X, self.features) - self.mean_) / self.scale_
        dist = ((z[:, None, :] - self.centroids_[None, :, :]) ** 2).sum(axis=2)
        return np.asarray(self.classes_, dtype=object)[np.argmin(dist, axis=1)]

    def describe(self) -> str:
        if self.centroids_ is None:
            return "unfitted"
        spread = self.centroids_.max(axis=0) - self.centroids_.min(axis=0)
        top = [self.features[i] for i in np.argsort(spread)[::-1][:3]]
        return f"nearest of {len(self.classes_)} class means; most separating: {', '.join(top)}"
