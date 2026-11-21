import sys

import numpy as np
import pandas as pd
import pytest

from pumpguard import models as models_mod
from pumpguard.benchmark import run_benchmark, synthetic_feature_table
from pumpguard.cli import main
from pumpguard.models import (
    LEARNED_MODELS,
    make_learned_model,
    require_sklearn,
    sklearn_available,
)


def _two_class_table(n=40, seed=0):
    """Feature `a` separates the classes; `b` is pure noise."""
    rng = np.random.default_rng(seed)
    y = np.array(["healthy"] * (n // 2) + ["damaged"] * (n // 2), dtype=object)
    a = np.where(y == "damaged", 5.0, 0.0) + rng.normal(0, 0.5, n)
    b = rng.normal(0, 1.0, n)
    return pd.DataFrame({"a": a, "b": b}), y


def _three_class_table(n_per=20, seed=0):
    rng = np.random.default_rng(seed)
    centres = {"healthy": (0.0, 0.0), "outer": (6.0, 0.0), "inner": (0.0, 6.0)}
    rows, y = [], []
    for label, (cx, cy) in centres.items():
        rows.append(np.column_stack([rng.normal(cx, 0.5, n_per), rng.normal(cy, 0.5, n_per)]))
        y += [label] * n_per
    return pd.DataFrame(np.vstack(rows), columns=["x", "z"]), np.array(y, dtype=object)


# ------------------------------------------------- tests that need no sklearn


@pytest.fixture
def no_sklearn(monkeypatch):
    """Make `import sklearn` fail, as on an install without the [ml] extra."""
    monkeypatch.setitem(sys.modules, "sklearn", None)


def test_missing_sklearn_gives_install_hint(no_sklearn):
    assert not sklearn_available()
    with pytest.raises(ImportError, match=r"pumpguard-ai\[ml\]"):
        require_sklearn()
    for name in LEARNED_MODELS:
        with pytest.raises(ImportError, match=r"\[ml\]"):
            make_learned_model(name, ["a"])


def test_benchmark_learned_without_sklearn_fails_before_any_work(no_sklearn):
    df = pd.DataFrame({"label": ["healthy"], "group_id": ["g"], "rms": [1.0]})
    with pytest.raises(ImportError, match=r"\[ml\]"):
        run_benchmark(df, features=["rms"], learned=True)


def test_cli_reports_missing_sklearn_cleanly(no_sklearn, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["benchmark", "--synthetic", "--learned", "--out", str(tmp_path)])
    assert exc.value.code == 2
    assert "[ml]" in capsys.readouterr().err


def test_core_import_does_not_load_sklearn():
    code = (
        "import sys, pumpguard, pumpguard.benchmark, pumpguard.leakage, pumpguard.models; "
        "assert not any(m == 'sklearn' or m.startswith('sklearn.') for m in sys.modules)"
    )
    import subprocess

    subprocess.run([sys.executable, "-c", code], check=True)


def test_unknown_learned_model_name():
    with pytest.raises(ValueError, match="unknown learned model"):
        make_learned_model("svm", ["a"])


# ------------------------------------------------------ tests with sklearn

sklearn_required = pytest.mark.skipif(not sklearn_available(), reason="needs the [ml] extra")


@sklearn_required
def test_logistic_regression_weights_the_informative_feature():
    X, y = _two_class_table()
    m = make_learned_model("logistic_regression", ["a", "b"]).fit(X, y)
    assert (m.predict(X) == y).mean() == 1.0
    coefs = m.coefficients()
    # Binary case: one coefficient row, reported for the second class in sorted order.
    assert list(coefs) == ["healthy"]
    assert coefs["healthy"]["a"] < 0  # larger `a` means less likely healthy
    assert abs(coefs["healthy"]["a"]) > 5 * abs(coefs["healthy"]["b"])
    assert m.describe().split("weights: ")[1].startswith("a (")
    assert m.hyperparameters()["class_weight"] == "balanced"


@sklearn_required
def test_logistic_regression_multiclass_has_one_row_per_class():
    X, y = _three_class_table()
    m = make_learned_model("logistic_regression", ["x", "z"]).fit(X, y)
    assert set(m.coefficients()) == {"healthy", "outer", "inner"}
    assert (m.predict(X) == y).mean() == 1.0


@sklearn_required
def test_random_forest_is_deterministic_and_finds_the_feature():
    X, y = _two_class_table()
    a = make_learned_model("random_forest", ["a", "b"], seed=3).fit(X, y)
    b = make_learned_model("random_forest", ["a", "b"], seed=3).fit(X, y)
    assert np.array_equal(a.predict(X), b.predict(X))
    assert a.importances() == b.importances()
    imp = a.importances()
    assert sum(imp.values()) == pytest.approx(1.0)
    assert imp["a"] > imp["b"]
    assert "a (" in a.describe()


@sklearn_required
def test_labels_keep_their_type():
    X, y = _two_class_table()
    y_int = np.where(y == "damaged", 1, 0)
    for name in LEARNED_MODELS:
        pred = make_learned_model(name, ["a", "b"]).fit(X, y_int).predict(X)
        assert pred.dtype == object
        assert set(pred) <= {0, 1}
        assert all(isinstance(v, (int, np.integer)) for v in pred)


@sklearn_required
@pytest.mark.parametrize("name", LEARNED_MODELS)
def test_learned_models_validate(name):
    X, y = _two_class_table()
    m = make_learned_model(name, ["a", "b"])
    assert m.describe() == "unfitted"
    with pytest.raises(RuntimeError, match="fit"):
        m.predict(X)
    with pytest.raises(ValueError, match="missing feature"):
        m.fit(X.drop(columns="b"), y)
    with pytest.raises(ValueError, match="non-finite"):
        m.fit(X.assign(a=np.nan), y)
    with pytest.raises(ValueError, match="two classes"):
        m.fit(X, np.full(len(y), "healthy", dtype=object))
    with pytest.raises(ValueError, match="equally long"):
        m.fit(X, y[:-1])
    with pytest.raises(ValueError, match="at least one feature"):
        make_learned_model(name, [])


@sklearn_required
def test_hyperparameter_validation_and_unfitted_accessors():
    with pytest.raises(ValueError, match="C must be"):
        models_mod.LogisticRegressionModel(["a"], C=0.0)
    with pytest.raises(ValueError, match="n_estimators"):
        models_mod.RandomForestModel(["a"], n_estimators=0)
    with pytest.raises(RuntimeError):
        models_mod.LogisticRegressionModel(["a"]).coefficients()
    with pytest.raises(RuntimeError):
        models_mod.RandomForestModel(["a"]).importances()


@sklearn_required
def test_benchmark_with_learned_models():
    df = synthetic_feature_table(seed=0, machines=4, segments=3)
    r = run_benchmark(df, n_boot=50, learned=True)
    assert r["learned"] is True
    for task in ("detection", "diagnosis"):
        rows = r["tasks"][task]
        learned = [x["baseline"] for x in rows if x["kind"] == "learned"]
        assert learned == list(LEARNED_MODELS)
        assert all(len(x["fitted_rules"]) == r["protocol_info"]["n_splits"] for x in rows)
        assert set(r["decision"][task]) == set(LEARNED_MODELS)
        for name in LEARNED_MODELS:
            assert f"{task}/{name}" in r["leakage_check"]
    assert set(r["learned_hyperparameters"]) == set(LEARNED_MODELS)
    # The same folds are used for every model.
    plain = run_benchmark(df, n_boot=50)
    assert plain["tasks"]["detection"][1] == r["tasks"]["detection"][1]
    assert "decision" not in plain


@sklearn_required
def test_cli_benchmark_learned(tmp_path, capsys):
    main(["benchmark", "--synthetic", "--learned", "--n-boot", "20", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "random_forest" in out
    assert "decision   detection/logistic_regression" in out
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Decision: learned models vs baselines" in report
    assert "hyperparameters fixed in advance" in report
