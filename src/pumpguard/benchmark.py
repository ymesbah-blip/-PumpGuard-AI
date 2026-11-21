"""Leakage-safe benchmark of transparent baselines (and optional learned models).

Input: one row per segment with a label column, a group column (the unit that
must not be split, e.g. a physical bearing) and feature columns. Optional
``split`` column ("train"/"test") selects a predefined split; otherwise
stratified group k-fold cross-validation is used.

Two tasks are evaluated when possible:

* **detection**: healthy vs damaged (any fault);
* **diagnosis**: healthy vs outer vs inner (only if labels allow).

Every score comes with a 95 % group-bootstrap interval, per-group and
per-operating-condition results (failure modes), and, for cross-validation, a
comparison with a deliberately leaky random-segment split.

With ``learned=True`` (needs the ``[ml]`` extra) logistic regression and a random
forest are evaluated on the same folds, and each is checked against every
baseline with the protocol's decision rule (``results["decision"]``).

The protocol is fixed in ``docs/benchmark-protocol.md``.
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
from .baselines import EnvelopeRule, MajorityClass, NearestCentroid, SingleFeatureThreshold
from .evaluation import (
    Fold,
    classification_metrics,
    group_bootstrap_ci,
    random_kfold,
    stratified_group_kfold,
)

__all__ = [
    "DEFAULT_FEATURES",
    "decide_against_baselines",
    "run_benchmark",
    "synthetic_feature_table",
    "write_report",
]

#: Transparent features used by the threshold and centroid baselines.
DEFAULT_FEATURES: tuple[str, ...] = (
    "rms",
    "kurtosis",
    "crest_factor",
    "impulse_factor",
    "spectral_centroid_hz",
    "hf_energy_ratio",
    "env_bpfo_ratio",
    "env_bpfi_ratio",
)

Model = Any  # objects with fit / predict / describe / name

_LEARNED = ("logistic_regression", "random_forest")


def _bal_acc(t: NDArray[np.object_], p: NDArray[np.object_]) -> float:
    return float(classification_metrics(t, p)["balanced_accuracy"])


def _macro_f1(t: NDArray[np.object_], p: NDArray[np.object_]) -> float:
    return float(classification_metrics(t, p)["macro_f1"])


def _predict_folds(
    factory: Callable[[], Model], X: pd.DataFrame, y: NDArray[np.object_], folds: Sequence[Fold]
) -> tuple[NDArray[np.object_], list[str]]:
    pred = np.empty(len(y), dtype=object)
    descriptions = []
    for train, test in folds:
        model = factory().fit(X.iloc[train], y[train])
        pred[test] = model.predict(X.iloc[test])
        descriptions.append(model.describe())
    return pred, descriptions


def _evaluate(
    name: str,
    factory: Callable[[], Model],
    X: pd.DataFrame,
    y: NDArray[np.object_],
    groups: NDArray[np.object_],
    folds: Sequence[Fold],
    labels: list[str],
    conditions: NDArray[np.object_] | None,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    tested = np.unique(np.concatenate([test for _, test in folds]))
    pred, descriptions = _predict_folds(factory, X, y, folds)
    t, p, g = y[tested], pred[tested], groups[tested]
    metrics = classification_metrics(t, p, labels)
    result: dict[str, Any] = {
        "baseline": name,
        "kind": "learned" if name in _LEARNED else "baseline",
        "fitted_rules": descriptions,
        "metrics": metrics,
        "ci95": {
            "balanced_accuracy": group_bootstrap_ci(t, p, g, _bal_acc, n_boot=n_boot, seed=seed),
            "macro_f1": group_bootstrap_ci(t, p, g, _macro_f1, n_boot=n_boot, seed=seed),
        },
    }
    per_group = (
        pd.DataFrame({"group": g, "label": t, "correct": t == p})
        .groupby(["group", "label"], sort=True)["correct"]
        .agg(["mean", "size"])
        .reset_index()
    )
    result["per_group"] = [
        {"group": r.group, "label": r.label, "accuracy": float(r.mean), "n": int(r.size)}
        for r in per_group.itertuples(index=False)
    ]
    if conditions is not None:
        c = conditions[tested]
        result["per_condition"] = {
            str(cond): _bal_acc(t[c == cond], p[c == cond]) for cond in sorted(set(c), key=str)
        }
    return result


def _protocol(
    df: pd.DataFrame, y: NDArray[np.object_], groups: NDArray[np.object_], n_splits: int, seed: int
) -> tuple[str, list[Fold], dict[str, Any]]:
    if "split" in df.columns:
        split = df["split"].astype(str).to_numpy()
        train, test = np.flatnonzero(split == "train"), np.flatnonzero(split == "test")
        if train.size == 0 or test.size == 0:
            raise ValueError("'split' column must contain both 'train' and 'test' rows")
        overlap = set(groups[train]) & set(groups[test])
        if overlap:
            raise ValueError(f"groups on both sides of the predefined split: {sorted(overlap)}")
        info = {
            "train_groups": sorted(set(groups[train]), key=str),
            "test_groups": sorted(set(groups[test]), key=str),
        }
        return "predefined_split", [(train, test)], info
    per_class = pd.Series(groups).groupby(y).nunique()
    k = int(max(2, min(n_splits, per_class.min())))
    folds = stratified_group_kfold(groups, y, n_splits=k, seed=seed)
    return "stratified_group_kfold", folds, {"n_splits": k, "groups_per_class": per_class.to_dict()}


def run_benchmark(
    df: pd.DataFrame,
    *,
    label_col: str = "label",
    group_col: str = "group_id",
    features: Sequence[str] = DEFAULT_FEATURES,
    healthy_label: str = "healthy",
    outer_label: str = "outer",
    inner_label: str = "inner",
    n_splits: int = 5,
    n_boot: int = 1000,
    seed: int = 0,
    learned: bool = False,
) -> dict[str, Any]:
    """Evaluate the transparent baselines; see the module docstring.

    ``learned=True`` adds logistic regression and a random forest (fixed
    hyperparameters, seeded with ``seed``) and raises ``ImportError`` without
    scikit-learn.
    """
    if learned:
        from .models import make_learned_model, require_sklearn

        require_sklearn()
    for col in (label_col, group_col, *features):
        if col not in df.columns:
            raise ValueError(f"feature table is missing column {col!r}")
    finite = np.isfinite(df[list(features)].to_numpy(dtype=np.float64)).all(axis=1)
    data = df.loc[finite].reset_index(drop=True)
    if data.empty:
        raise ValueError("no rows with finite values in all features")
    y = data[label_col].astype(str).to_numpy(dtype=object)
    groups = data[group_col].astype(str).to_numpy(dtype=object)
    if healthy_label not in set(y):
        raise ValueError(f"no '{healthy_label}' rows: detection needs healthy references")
    conditions = (
        data["operating_condition"].astype(str).to_numpy(dtype=object)
        if "operating_condition" in data.columns
        else None
    )
    X = data[list(features)]
    protocol, folds, protocol_info = _protocol(data, y, groups, n_splits, seed)

    summary = (
        data.assign(_label=y, _group=groups)
        .groupby("_label")
        .agg(groups=("_group", "nunique"), segments=("_group", "size"))
    )
    results: dict[str, Any] = {
        "pumpguard_version": __version__,
        "protocol": protocol,
        "protocol_info": protocol_info,
        "seed": seed,
        "n_boot": n_boot,
        "features": list(features),
        "learned": learned,
        "n_rows_dropped_nonfinite": int((~finite).sum()),
        "data_summary": {
            str(k): {"groups": int(v.groups), "segments": int(v.segments)}
            for k, v in summary.iterrows()
        },
        "tasks": {},
    }

    def evaluate(
        name: str, factory: Callable[[], Model], y_task: NDArray[np.object_], labels: list[str]
    ) -> dict[str, Any]:
        return _evaluate(name, factory, X, y_task, groups, folds, labels, conditions, n_boot, seed)

    # Detection: healthy vs damaged.
    y_det = np.where(y == healthy_label, healthy_label, "damaged").astype(object)
    det_labels = [healthy_label, "damaged"]
    det_models: list[tuple[str, Callable[[], Model]]] = [
        ("majority_class", MajorityClass),
        ("single_feature_threshold", lambda: SingleFeatureThreshold(features, healthy_label)),
        ("envelope_rule", lambda: EnvelopeRule("detection", healthy_label=healthy_label)),
    ]
    learned_models: list[tuple[str, Callable[[], Model]]] = []
    if learned:
        learned_models = [
            (name, partial(make_learned_model, name, features, seed=seed)) for name in _LEARNED
        ]
        results["learned_hyperparameters"] = {
            name: factory().hyperparameters() for name, factory in learned_models
        }
    det_models += learned_models
    results["tasks"]["detection"] = [evaluate(n, f, y_det, det_labels) for n, f in det_models]

    # Diagnosis: healthy / outer / inner.
    diag_labels = [healthy_label, outer_label, inner_label]
    if set(y) <= set(diag_labels) and len(set(y)) == 3:
        diag_models: list[tuple[str, Callable[[], Model]]] = [
            ("majority_class", MajorityClass),
            (
                "envelope_rule",
                lambda: EnvelopeRule(
                    healthy_label=healthy_label, outer_label=outer_label, inner_label=inner_label
                ),
            ),
            ("nearest_centroid", lambda: NearestCentroid(features)),
            *learned_models,
        ]
        results["tasks"]["diagnosis"] = [evaluate(n, f, y, diag_labels) for n, f in diag_models]
    else:
        results["diagnosis_skipped"] = (
            f"labels {sorted(set(y))} are not exactly {diag_labels}; diagnosis not evaluated"
        )

    # Leakage check: the same baselines with a random split that ignores groups.
    if protocol == "stratified_group_kfold":
        leaky = random_kfold(len(y), n_splits=len(folds), seed=seed)
        check = {}
        for task, y_task, models in (
            ("detection", y_det, det_models),
            *((("diagnosis", y, diag_models),) if "diagnosis" in results["tasks"] else ()),
        ):
            for name, factory in models:
                if name == "majority_class":
                    continue
                pred, _ = _predict_folds(factory, X, y_task, leaky)
                group_score = next(r for r in results["tasks"][task] if r["baseline"] == name)[
                    "metrics"
                ]["balanced_accuracy"]
                random_score = _bal_acc(y_task, pred)
                check[f"{task}/{name}"] = {
                    "group_kfold_balanced_accuracy": group_score,
                    "random_segment_kfold_balanced_accuracy": random_score,
                    "inflation": random_score - group_score,
                }
        results["leakage_check"] = check
    if learned:
        results["decision"] = {
            task: decide_against_baselines(rows) for task, rows in results["tasks"].items()
        }
    return results


def decide_against_baselines(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Apply the protocol's decision rule to each learned model of one task.

    A learned model is *meaningfully better* than a baseline only if its lower
    95 % bound of balanced accuracy exceeds the baseline's point estimate. It
    "beats all baselines" only if that holds for every baseline.
    """
    baselines = [r for r in rows if r.get("kind", "baseline") == "baseline"]
    out: dict[str, Any] = {}
    for r in rows:
        if r.get("kind") != "learned":
            continue
        low = float(r["ci95"]["balanced_accuracy"][0])
        versus = {
            b["baseline"]: {
                "baseline_balanced_accuracy": float(b["metrics"]["balanced_accuracy"]),
                "model_ci95_low": low,
                "meaningfully_better": low > float(b["metrics"]["balanced_accuracy"]),
            }
            for b in baselines
        }
        out[r["baseline"]] = {
            "beats_all_baselines": bool(versus)
            and all(v["meaningfully_better"] for v in versus.values()),
            "versus": versus,
        }
    return out


def synthetic_feature_table(
    seed: int = 0,
    machines: int = 5,
    segments: int = 4,
    *,
    severity_range: tuple[float, float] = (0.5, 1.5),
) -> pd.DataFrame:
    """Dry-run table with the same structure as a real 3-class bearing task.

    Synthetic healthy / outer-race / inner-race signals from virtual machines.
    Useful for testing the pipeline, never as evidence of diagnostic performance.
    A low ``severity_range`` (e.g. 0.05-0.15) makes faults subtle relative to
    machine-to-machine differences, which is the regime where leakage shows.
    """
    from .dataset import make_synthetic_dataset

    df = make_synthetic_dataset(
        conditions=("healthy", "bearing_outer", "bearing_inner"),
        machines_per_condition=machines,
        segments_per_machine=segments,
        severity_range=severity_range,
        duration=0.5,
        seed=seed,
    )
    mapping = {"healthy": "healthy", "bearing_outer": "outer", "bearing_inner": "inner"}
    return df.assign(label=df["condition"].map(mapping))


# -------------------------------------------------------------------- report


def _fmt(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def _ci(ci: Sequence[float]) -> str:
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def _report_markdown(results: dict[str, Any], dataset: dict[str, Any] | None) -> str:
    lines: list[str] = []
    title = dataset.get("dataset_id", "dataset") if dataset else "feature table"
    task = dataset.get("task", "") if dataset else ""
    lines += [f"# Benchmark report: {title} {task}".rstrip(), ""]
    if results.get("learned"):
        lines += [
            "> **Read this first.** Transparent baselines and learned models (scikit-learn, "
            "hyperparameters fixed in advance) evaluated on the same leakage-safe folds. "
            "Intervals come from a bootstrap over groups.",
        ]
    else:
        lines += [
            "> **Read this first.** These are transparent, non-ML baselines evaluated with a "
            "leakage-safe split. Intervals come from a bootstrap over groups.",
        ]
    if dataset and dataset.get("synthetic"):
        lines += ["> **Synthetic data**: a pipeline dry run, not evidence of real performance."]
    if dataset and dataset.get("machine_type"):
        lines += [
            f"> Data come from a {dataset['machine_type']}. They do **not** validate "
            "diagnosis of centrifugal pumps in the field.",
        ]
    lines += [""]

    lines += ["## Data", "", "| Class | Groups | Segments |", "|---|---|---|"]
    for label, s in results["data_summary"].items():
        lines.append(f"| {label} | {s['groups']} | {s['segments']} |")
    lines += [
        "",
        f"Rows dropped for non-finite features: {results['n_rows_dropped_nonfinite']}.",
        "",
        "## Protocol",
        "",
        f"- Split: `{results['protocol']}` {json.dumps(results['protocol_info'], default=str)}",
        f"- Features: {', '.join(f'`{f}`' for f in results['features'])}",
        f"- Seed {results['seed']}, {results['n_boot']} group-bootstrap replicates, 95 % "
        "percentile intervals",
        "",
    ]

    for task, rows in results["tasks"].items():
        lines += [
            f"## Results: {task}",
            "",
            "| Model | Balanced accuracy [95 % CI] | Macro-F1 [95 % CI] | Fitted (first fold) |",
            "|---|---|---|---|",
        ]
        for r in rows:
            m, ci = r["metrics"], r["ci95"]
            lines.append(
                f"| {r['baseline']} | {_fmt(m['balanced_accuracy'])} {_ci(ci['balanced_accuracy'])}"
                f" | {_fmt(m['macro_f1'])} {_ci(ci['macro_f1'])} | {r['fitted_rules'][0]} |"
            )
        lines.append("")
        for r in rows:
            labels = r["metrics"]["labels"]
            lines += [
                f"<details><summary>{r['baseline']}: confusion matrix and failure modes</summary>",
                "",
                "| true \\ predicted | " + " | ".join(labels) + " |",
                "|---" * (len(labels) + 1) + "|",
            ]
            for label, row in zip(labels, r["metrics"]["confusion_matrix"], strict=True):
                lines.append(f"| {label} | " + " | ".join(str(v) for v in row) + " |")
            weak = [g for g in r["per_group"] if g["accuracy"] < 0.5]
            lines += ["", f"Groups with accuracy < 0.5: {len(weak)} of {len(r['per_group'])}"]
            lines += [f"- `{g['group']}` ({g['label']}): {g['accuracy']:.2f}" for g in weak]
            if r.get("per_condition"):
                lines += ["", "Balanced accuracy per operating condition:"]
                lines += [f"- `{c}`: {_fmt(v)}" for c, v in r["per_condition"].items()]
            lines += ["", "</details>", ""]

    if "diagnosis_skipped" in results:
        lines += [f"_Diagnosis not evaluated: {results['diagnosis_skipped']}_", ""]

    if "decision" in results:
        lines += [
            "## Decision: learned models vs baselines",
            "",
            "Protocol rule: a learned model is meaningfully better than a baseline only if its "
            "lower 95 % bound exceeds the baseline's point estimate, and is worth reporting as "
            "an improvement only if that holds against **every** baseline.",
            "",
            "| Task / model | Lower 95 % bound | Beats all baselines | Baselines not beaten |",
            "|---|---|---|---|",
        ]
        for task, models in results["decision"].items():
            for name, d in models.items():
                low = next(iter(d["versus"].values()))["model_ci95_low"] if d["versus"] else None
                missed = [b for b, v in d["versus"].items() if not v["meaningfully_better"]]
                lines.append(
                    f"| {task}/{name} | {_fmt(low) if low is not None else 'n/a'} | "
                    f"{'yes' if d['beats_all_baselines'] else 'no'} | "
                    f"{', '.join(missed) if missed else '-'} |"
                )
        lines.append("")

    if "leakage_check" in results:
        lines += [
            "## Leakage check",
            "",
            "The same baselines with a random segment split that ignores groups. The gap shows "
            "how much a leaky protocol would overstate performance.",
            "",
            "| Task / baseline | Group k-fold | Random segments | Inflation |",
            "|---|---|---|---|",
        ]
        for key, v in results["leakage_check"].items():
            lines.append(
                f"| {key} | {_fmt(v['group_kfold_balanced_accuracy'])} | "
                f"{_fmt(v['random_segment_kfold_balanced_accuracy'])} | {v['inflation']:+.3f} |"
            )
        lines.append("")

    lines += [
        "## Limitations",
        "",
        "- Few independent groups: intervals are wide; small differences between baselines are "
        "not meaningful.",
        "- Thresholds and centroids are fitted per training fold; the rules shown are from the "
        "first fold only (all folds are in `results.json`).",
        *(
            [
                "- Learned models use fixed hyperparameters (see `results.json`); none were tuned. "
                "Random-forest importances are impurity-based, computed on training data, and "
                "biased toward continuous features: they are hints, not evidence.",
            ]
            if results.get("learned")
            else []
        ),
        "- Envelope features use a fixed demodulation band and nominal bearing geometry "
        "(1-2 % manufacturer variation); no band optimisation was performed.",
        "",
    ]
    if dataset:
        lines += [
            "## Data source and licence",
            "",
            f"- Source: {dataset.get('source_url', 'n/a')}",
            f"- Licence: {dataset.get('license', 'n/a')}",
            f"- Cite: {dataset.get('citation', 'n/a')}",
            f"- Files used: {dataset.get('n_files_used', 'n/a')}, failed: "
            f"{len(dataset.get('failures', []))}, missing bearings: "
            f"{dataset.get('missing_bearings', [])}",
            "",
        ]
    lines += [f"_Generated by pumpguard {results['pumpguard_version']}._", ""]
    return "\n".join(lines)


def write_report(
    results: dict[str, Any], out_dir: str | Path, dataset: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    """Write ``results.json`` and ``report.md`` into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"results": results, "dataset": dataset}
    json_path = out / "results.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path = out / "report.md"
    md_path.write_text(_report_markdown(results, dataset), encoding="utf-8")
    return json_path, md_path
