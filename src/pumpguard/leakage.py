"""Experiment: the same model under a random split vs a split by group.

Research question (roadmap v0.4): how much does a record-level random split
overstate a model's score compared with a split that keeps every group
(machine, bearing, recording day) on one side?

For each repeat ``r`` the same model, features and labels are evaluated twice,
with fold seed ``seed + r``:

* **group k-fold** (:func:`~pumpguard.evaluation.stratified_group_kfold`): every
  group is tested by a model that never saw it;
* **random k-fold** (:func:`~pumpguard.evaluation.random_kfold`): segments are
  shuffled regardless of group, so neighbours of a test segment sit in training.

``inflation = random − group`` (balanced accuracy). Positive inflation in most
repeats means the model exploits information shared within a group that does not
transfer to new groups: unit identity, mounting, an individual defect, a
recording day.

Repeats vary the fold assignment (and the random forest's seed). They show how
stable the gap is for *this* table, not how it would change with other units.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from ._version import __version__
from .baselines import NearestCentroid
from .benchmark import DEFAULT_FEATURES
from .evaluation import classification_metrics, random_kfold, stratified_group_kfold
from .models import LEARNED_MODELS, make_learned_model, sklearn_available

__all__ = ["SPLIT_MODELS", "compare_splits", "write_leakage_report"]

#: Models the experiment can run. ``nearest_centroid`` needs no optional extra.
SPLIT_MODELS: tuple[str, ...] = ("nearest_centroid", *LEARNED_MODELS)


def _factory(name: str, features: Sequence[str], seed: int) -> Callable[[], Any]:
    if name == "nearest_centroid":
        return partial(NearestCentroid, features)
    return partial(make_learned_model, name, features, seed)


def _cv_balanced_accuracy(
    factory: Callable[[], Any],
    X: pd.DataFrame,
    y: NDArray[np.object_],
    folds: Sequence[tuple[NDArray[np.intp], NDArray[np.intp]]],
) -> float:
    pred = np.empty(len(y), dtype=object)
    for train, test in folds:
        pred[test] = factory().fit(X.iloc[train], y[train]).predict(X.iloc[test])
    return float(classification_metrics(y, pred)["balanced_accuracy"])


def compare_splits(
    df: pd.DataFrame,
    *,
    label_col: str = "label",
    group_col: str = "group_id",
    features: Sequence[str] = DEFAULT_FEATURES,
    models: Sequence[str] | None = None,
    n_repeats: int = 5,
    n_splits: int = 5,
    seed: int = 0,
) -> dict[str, Any]:
    """Run the random-vs-group split experiment; see the module docstring.

    ``models=None`` runs every model in :data:`SPLIT_MODELS` that can be imported
    and lists the others under ``"skipped_models"``. Naming a learned model
    explicitly without scikit-learn raises ``ImportError``.
    """
    if n_repeats < 1:
        raise ValueError("n_repeats must be >= 1")
    for col in (label_col, group_col, *features):
        if col not in df.columns:
            raise ValueError(f"feature table is missing column {col!r}")
    skipped: dict[str, str] = {}
    if models is None:
        chosen = [m for m in SPLIT_MODELS if m == "nearest_centroid" or sklearn_available()]
        skipped = {m: "scikit-learn not installed" for m in SPLIT_MODELS if m not in chosen}
    else:
        chosen = list(dict.fromkeys(models))
        unknown = [m for m in chosen if m not in SPLIT_MODELS]
        if unknown or not chosen:
            raise ValueError(f"models must be a non-empty subset of {list(SPLIT_MODELS)}")
        if any(m in LEARNED_MODELS for m in chosen):
            from .models import require_sklearn

            require_sklearn()

    finite = np.isfinite(df[list(features)].to_numpy(dtype=np.float64)).all(axis=1)
    data = df.loc[finite].reset_index(drop=True)
    if data.empty:
        raise ValueError("no rows with finite values in all features")
    y = data[label_col].astype(str).to_numpy(dtype=object)
    groups = data[group_col].astype(str).to_numpy(dtype=object)
    labels = sorted(set(y))
    if len(labels) < 2:
        raise ValueError("at least two classes are needed")
    groups_per_class = pd.Series(groups).groupby(y).nunique()
    k = int(min(n_splits, groups_per_class.min()))
    if k < 2:
        raise ValueError("every class needs at least two groups for group k-fold")
    X = data[list(features)]

    per_model: dict[str, dict[str, Any]] = {}
    for name in chosen:
        group_scores, random_scores = [], []
        for r in range(n_repeats):
            fold_seed = seed + r
            factory = _factory(name, features, fold_seed)
            gf = stratified_group_kfold(groups, y, n_splits=k, seed=fold_seed)
            rf = random_kfold(len(y), n_splits=k, seed=fold_seed)
            group_scores.append(_cv_balanced_accuracy(factory, X, y, gf))
            random_scores.append(_cv_balanced_accuracy(factory, X, y, rf))
        g, rnd = np.array(group_scores), np.array(random_scores)
        infl = rnd - g
        per_model[name] = {
            "group_kfold": g.tolist(),
            "random_kfold": rnd.tolist(),
            "inflation": infl.tolist(),
            "summary": {
                "group_mean": float(g.mean()),
                "random_mean": float(rnd.mean()),
                "inflation_mean": float(infl.mean()),
                "inflation_min": float(infl.min()),
                "inflation_max": float(infl.max()),
                "repeats_inflated": int((infl > 0).sum()),
            },
        }

    return {
        "pumpguard_version": __version__,
        "question": "How much does a random segment split overstate the group-split score?",
        "labels": labels,
        "chance_balanced_accuracy": 1.0 / len(labels),
        "n_rows": len(y),
        "n_rows_dropped_nonfinite": int((~finite).sum()),
        "groups_per_class": {str(c): int(n) for c, n in groups_per_class.items()},
        "features": list(features),
        "n_splits": k,
        "n_repeats": n_repeats,
        "seed": seed,
        "models": per_model,
        "skipped_models": skipped,
    }


# -------------------------------------------------------------------- report


def _f(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{x:.3f}"


def _report_markdown(results: dict[str, Any], dataset: dict[str, Any] | None) -> str:
    title = dataset.get("dataset_id", "feature table") if dataset else "feature table"
    chance = results["chance_balanced_accuracy"]
    lines = [f"# Leakage experiment: {title}", ""]
    lines += [f"> {results['question']}"]
    if dataset and dataset.get("synthetic"):
        lines += [
            "> **Synthetic data.** The size of the gap depends on the generator settings "
            f"({dataset.get('settings', 'see results JSON')}). It demonstrates the mechanism; "
            "it is not an estimate for any real dataset."
        ]
    lines += [
        "",
        "## Setup",
        "",
        f"- Rows: {results['n_rows']} (dropped for non-finite features: "
        f"{results['n_rows_dropped_nonfinite']}); groups per class: "
        f"{json.dumps(results['groups_per_class'])}",
        f"- {results['n_splits']}-fold, {results['n_repeats']} repeats (fold seeds "
        f"{results['seed']}..{results['seed'] + results['n_repeats'] - 1}); chance balanced "
        f"accuracy {chance:.3f}",
        f"- Features: {', '.join(f'`{f}`' for f in results['features'])}",
        "",
        "## Results (balanced accuracy, mean over repeats)",
        "",
        "| Model | Group k-fold | Random k-fold | Inflation mean [min, max] | Repeats inflated |",
        "|---|---|---|---|---|",
    ]
    below_chance = []
    for name, m in results["models"].items():
        s = m["summary"]
        lines.append(
            f"| {name} | {_f(s['group_mean'])} | {_f(s['random_mean'])} | "
            f"{s['inflation_mean']:+.3f} [{s['inflation_min']:+.3f}, {s['inflation_max']:+.3f}] | "
            f"{s['repeats_inflated']} of {results['n_repeats']} |"
        )
        if s["group_mean"] < chance - 0.05:
            below_chance.append(name)
    if results.get("skipped_models"):
        lines += [
            "",
            "Skipped: " + ", ".join(f"`{k}` ({v})" for k, v in results["skipped_models"].items()),
        ]
    lines += [
        "",
        "## How to read this",
        "",
        "- Only the **group k-fold** column estimates performance on units the model has not "
        "seen. Never report the random-split column as a result.",
        "- Inflation that is positive in most repeats means segments of one group share "
        "information unrelated to the label (unit identity, mounting, an individual defect) and "
        "the model uses it. Flexible models (random forest) usually exploit it more than simple "
        "ones.",
        "- Small or negative inflation does not prove the absence of leakage in other data. It "
        "only says this table, with these features, shows no gap.",
    ]
    if below_chance:
        lines += [
            f"- Group k-fold below chance for {', '.join(below_chance)}: the features identify "
            "groups but carry little class information that transfers. Holding out whole groups "
            "leaves the training fold short of the held-out class, which pushes predictions away "
            "from it. Read this as *no evidence of generalisation*, not as anti-information.",
        ]
    lines += ["", f"_Generated by pumpguard {results['pumpguard_version']}._", ""]
    return "\n".join(lines)


def write_leakage_report(
    results: dict[str, Any], out_dir: str | Path, dataset: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    """Write ``leakage.json`` and ``leakage.md`` into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "leakage.json"
    payload = {"results": results, "dataset": dataset}
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path = out / "leakage.md"
    md_path.write_text(_report_markdown(results, dataset), encoding="utf-8")
    return json_path, md_path
