"""Learned classifiers on the transparent features (optional ``[ml]`` extra).

Install with ``pip install "pumpguard-ai[ml]"`` (adds scikit-learn). The core package
never imports scikit-learn; this module only touches it when a model is created.

Both models follow the interface of :mod:`pumpguard.baselines` (``name``, ``fit``,
``predict``, ``describe``), so :func:`pumpguard.benchmark.run_benchmark` evaluates
them under exactly the same folds, metrics and group-bootstrap intervals.

Hyperparameters are **fixed in advance** (``docs/benchmark-protocol.md``,
amendment 1). They are never tuned on test folds. Tuning on the same folds that
produce the reported score is another form of leakage.

* :class:`LogisticRegressionModel`: z-scored features, L2-regularised logistic
  regression, balanced class weights. Linear, so its coefficients can be read.
* :class:`RandomForestModel`: random forest with balanced class weights and a
  minimum leaf size, so it cannot isolate single segments.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from .baselines import _labels, _matrix

__all__ = [
    "LEARNED_MODELS",
    "LogisticRegressionModel",
    "RandomForestModel",
    "make_learned_model",
    "require_sklearn",
    "sklearn_available",
]

#: Names accepted by :func:`make_learned_model`, in reporting order.
LEARNED_MODELS: tuple[str, ...] = ("logistic_regression", "random_forest")

_INSTALL_HINT = 'install the optional extra: pip install "pumpguard-ai[ml]"'


def sklearn_available() -> bool:
    """True if scikit-learn can be imported (without importing it)."""
    try:
        return importlib.util.find_spec("sklearn") is not None
    except (ImportError, ValueError):
        return False


def require_sklearn() -> ModuleType:
    """Import scikit-learn or raise ``ImportError`` explaining how to install it."""
    try:
        return importlib.import_module("sklearn")
    except ImportError as exc:
        raise ImportError(f"learned models need scikit-learn; {_INSTALL_HINT}") from exc


def _top(weights: NDArray[np.float64], k: int = 3) -> list[int]:
    return [int(i) for i in np.argsort(-weights, kind="stable")[:k]]


class _LearnedModel:
    """Shared fit/predict plumbing; subclasses build the scikit-learn estimator."""

    name = "learned"

    def __init__(self, features: Sequence[str], seed: int = 0) -> None:
        require_sklearn()
        if not features:
            raise ValueError("at least one feature is required")
        self.features = list(features)
        self.seed = int(seed)
        self.estimator_: Any = None
        self.classes_: list[Any] = []

    def _build(self) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def hyperparameters(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def fit(self, X: pd.DataFrame, y: ArrayLike) -> _LearnedModel:
        labels = _labels(y)
        values = _matrix(X, self.features)
        if values.shape[0] != labels.size or labels.size == 0:
            raise ValueError("X and y must be non-empty and equally long")
        classes = sorted(set(labels), key=str)
        if len(classes) < 2:
            raise ValueError(f"at least two classes are needed to fit {self.name}")
        # Fit on integer codes: scikit-learn mishandles mixed object labels and
        # numeric-looking strings (e.g. "0") in class_weight; map back in predict().
        code = {c: i for i, c in enumerate(classes)}
        estimator = self._build()
        estimator.fit(values, np.array([code[v] for v in labels], dtype=np.int64))
        self.estimator_ = estimator
        self.classes_ = classes
        return self

    def predict(self, X: pd.DataFrame) -> NDArray[np.object_]:
        if self.estimator_ is None:
            raise RuntimeError("fit() must be called before predict()")
        pred = self.estimator_.predict(_matrix(X, self.features))
        return np.asarray([self.classes_[int(i)] for i in pred], dtype=object)


class LogisticRegressionModel(_LearnedModel):
    """Standardise with training-fold statistics, then multinomial logistic regression."""

    name = "logistic_regression"

    def __init__(self, features: Sequence[str], *, C: float = 1.0, seed: int = 0) -> None:
        super().__init__(features, seed)
        if not (np.isfinite(C) and C > 0):
            raise ValueError("C must be a finite positive number")
        self.C = float(C)

    def hyperparameters(self) -> dict[str, Any]:
        return {
            "scaling": "z-score (training fold)",
            "penalty": "l2",
            "C": self.C,
            "class_weight": "balanced",
            "max_iter": 5000,
        }

    def _build(self) -> Any:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=self.C, class_weight="balanced", max_iter=5000, random_state=self.seed
            ),
        )

    def coefficients(self) -> dict[str, dict[str, float]]:
        """Coefficients on z-scored features: ``{class: {feature: coef}}``.

        For two classes scikit-learn stores one row (for the second class in
        sorted order); it is reported under that class.
        """
        if self.estimator_ is None:
            raise RuntimeError("fit() must be called before coefficients()")
        lr = self.estimator_[-1]
        coef = np.atleast_2d(np.asarray(lr.coef_, dtype=np.float64))
        names = [str(self.classes_[int(i)]) for i in lr.classes_]
        rows = names[1:] if coef.shape[0] == 1 else names
        return {
            cls: {f: float(w) for f, w in zip(self.features, coef[i], strict=True)}
            for i, cls in enumerate(rows)
        }

    def describe(self) -> str:
        if self.estimator_ is None:
            return "unfitted"
        coefs = self.coefficients()
        weight = np.max(np.abs([list(c.values()) for c in coefs.values()]), axis=0)
        parts = []
        for i in _top(weight):
            cls, w = max(
                ((c, v[self.features[i]]) for c, v in coefs.items()), key=lambda t: abs(t[1])
            )
            parts.append(f"{self.features[i]} ({w:+.2f} for {cls})")
        return f"logistic regression (C={self.C:g}); largest z-score weights: " + ", ".join(parts)


class RandomForestModel(_LearnedModel):
    """Random forest with balanced class weights; deterministic for a given seed."""

    name = "random_forest"

    def __init__(
        self,
        features: Sequence[str],
        *,
        n_estimators: int = 300,
        min_samples_leaf: int = 3,
        seed: int = 0,
    ) -> None:
        super().__init__(features, seed)
        if n_estimators < 1 or min_samples_leaf < 1:
            raise ValueError("n_estimators and min_samples_leaf must be >= 1")
        self.n_estimators = int(n_estimators)
        self.min_samples_leaf = int(min_samples_leaf)

    def hyperparameters(self) -> dict[str, Any]:
        return {
            "n_estimators": self.n_estimators,
            "min_samples_leaf": self.min_samples_leaf,
            "max_features": "sqrt",
            "class_weight": "balanced",
            "random_state": self.seed,
        }

    def _build(self) -> Any:
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=self.n_estimators,
            min_samples_leaf=self.min_samples_leaf,
            max_features="sqrt",
            class_weight="balanced",
            random_state=self.seed,
            n_jobs=1,
        )

    def importances(self) -> dict[str, float]:
        """Mean impurity decrease per feature (sums to 1).

        Impurity importance is biased toward features with many distinct values
        and is computed on training data. Read it as a hint, not as evidence
        that a feature carries the fault information.
        """
        if self.estimator_ is None:
            raise RuntimeError("fit() must be called before importances()")
        imp = np.asarray(self.estimator_.feature_importances_, dtype=np.float64)
        return {f: float(v) for f, v in zip(self.features, imp, strict=True)}

    def describe(self) -> str:
        if self.estimator_ is None:
            return "unfitted"
        imp = self.importances()
        weight = np.array([imp[f] for f in self.features])
        top = ", ".join(f"{self.features[i]} ({weight[i]:.2f})" for i in _top(weight))
        return (
            f"random forest ({self.n_estimators} trees, min leaf {self.min_samples_leaf}); "
            f"top impurity importances: {top}"
        )


def make_learned_model(name: str, features: Sequence[str], seed: int = 0) -> _LearnedModel:
    """Create a learned model by name with the protocol's fixed hyperparameters."""
    if name == "logistic_regression":
        return LogisticRegressionModel(features, seed=seed)
    if name == "random_forest":
        return RandomForestModel(features, seed=seed)
    raise ValueError(f"unknown learned model {name!r}; choose from {list(LEARNED_MODELS)}")
