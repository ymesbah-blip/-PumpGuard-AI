import json

import numpy as np
import pandas as pd
import pytest

from pumpguard import leakage
from pumpguard.benchmark import decide_against_baselines, synthetic_feature_table
from pumpguard.cli import main
from pumpguard.leakage import compare_splits, write_leakage_report
from pumpguard.models import sklearn_available


@pytest.fixture(scope="module")
def synthetic_df():
    return synthetic_feature_table(seed=0, machines=4, segments=3)


def _fingerprint_table(n_groups=12, segments=6, seed=0):
    """Features identify the group; labels are assigned to groups at random.

    There is no class information that transfers to a new group, so an honest
    split must score near (or below) chance, while a random segment split can
    recognise groups it has already seen.
    """
    rng = np.random.default_rng(seed)
    labels = np.array(["a", "b"] * (n_groups // 2), dtype=object)
    rng.shuffle(labels)
    rows = []
    for g in range(n_groups):
        centre = rng.uniform(-10, 10, size=2)
        for _ in range(segments):
            x, z = centre + rng.normal(0, 0.05, size=2)
            rows.append({"group_id": f"g{g:02d}", "label": labels[g], "x": x, "z": z})
    return pd.DataFrame(rows)


def test_structure_with_core_model(synthetic_df):
    r = compare_splits(synthetic_df, models=["nearest_centroid"], n_repeats=3, n_splits=4)
    assert r["labels"] == ["healthy", "inner", "outer"]
    assert r["chance_balanced_accuracy"] == pytest.approx(1 / 3)
    assert r["n_splits"] == 4
    assert r["n_rows"] == len(synthetic_df)
    m = r["models"]["nearest_centroid"]
    assert len(m["group_kfold"]) == len(m["random_kfold"]) == len(m["inflation"]) == 3
    assert np.allclose(np.subtract(m["random_kfold"], m["group_kfold"]), m["inflation"])
    s = m["summary"]
    assert s["inflation_min"] <= s["inflation_mean"] <= s["inflation_max"]
    assert 0 <= s["repeats_inflated"] <= 3
    assert r["skipped_models"] == {}


def test_reproducible(synthetic_df):
    a = compare_splits(synthetic_df, models=["nearest_centroid"], n_repeats=2)
    b = compare_splits(synthetic_df, models=["nearest_centroid"], n_repeats=2)
    assert a == b


def test_k_is_capped_by_groups_per_class(synthetic_df):
    r = compare_splits(synthetic_df, models=["nearest_centroid"], n_repeats=1, n_splits=10)
    assert r["n_splits"] == 4  # four machines per class


def test_default_models_skip_learned_without_sklearn(synthetic_df, monkeypatch):
    monkeypatch.setattr(leakage, "sklearn_available", lambda: False)
    r = compare_splits(synthetic_df, n_repeats=1)
    assert list(r["models"]) == ["nearest_centroid"]
    assert set(r["skipped_models"]) == {"logistic_regression", "random_forest"}


def test_validation(synthetic_df):
    with pytest.raises(ValueError, match="n_repeats"):
        compare_splits(synthetic_df, n_repeats=0)
    with pytest.raises(ValueError, match="subset"):
        compare_splits(synthetic_df, models=["svm"])
    with pytest.raises(ValueError, match="subset"):
        compare_splits(synthetic_df, models=[])
    with pytest.raises(ValueError, match="missing column"):
        compare_splits(synthetic_df.drop(columns="rms"), models=["nearest_centroid"])
    one_class = synthetic_df[synthetic_df["label"] == "healthy"]
    with pytest.raises(ValueError, match="two classes"):
        compare_splits(one_class, models=["nearest_centroid"])
    single_group = synthetic_df[
        (synthetic_df["label"] != "inner") | (synthetic_df["group_id"] == "bearing_inner-m00")
    ]
    with pytest.raises(ValueError, match="two groups"):
        compare_splits(single_group, models=["nearest_centroid"])
    with pytest.raises(ValueError, match="no rows"):
        compare_splits(synthetic_df.assign(rms=np.nan), models=["nearest_centroid"])


def test_nonfinite_rows_are_dropped_and_counted(synthetic_df):
    df = synthetic_df.copy()
    df.loc[0, "kurtosis"] = np.inf
    r = compare_splits(df, models=["nearest_centroid"], n_repeats=1)
    assert r["n_rows_dropped_nonfinite"] == 1
    assert r["n_rows"] == len(df) - 1


@pytest.mark.skipif(not sklearn_available(), reason="needs the [ml] extra")
def test_random_split_rewards_memorising_groups():
    df = _fingerprint_table()
    r = compare_splits(df, features=["x", "z"], models=["random_forest"], n_repeats=3, n_splits=3)
    s = r["models"]["random_forest"]["summary"]
    assert s["random_mean"] > 0.9  # recognises groups seen in training
    assert s["group_mean"] < 0.7  # nothing transfers to unseen groups
    assert s["repeats_inflated"] == 3
    assert s["inflation_min"] > 0.2


def test_report_files_and_notes(tmp_path):
    df = _fingerprint_table()
    r = compare_splits(df, features=["x", "z"], models=["nearest_centroid"], n_repeats=2)
    r["models"]["nearest_centroid"]["summary"]["group_mean"] = 0.2  # force the below-chance note
    json_path, md_path = write_leakage_report(
        r, tmp_path / "out", {"dataset_id": "toy", "synthetic": True, "settings": "toy settings"}
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset"]["dataset_id"] == "toy"
    md = md_path.read_text(encoding="utf-8")
    assert md.startswith("# Leakage experiment: toy")
    assert "**Synthetic data.**" in md
    assert "toy settings" in md
    assert "| nearest_centroid |" in md
    assert "Never report the random-split column" in md
    assert "below chance for nearest_centroid" in md


def test_report_lists_skipped_models(tmp_path, synthetic_df, monkeypatch):
    monkeypatch.setattr(leakage, "sklearn_available", lambda: False)
    r = compare_splits(synthetic_df, n_repeats=1)
    _, md_path = write_leakage_report(r, tmp_path)
    assert "Skipped: `logistic_regression`" in md_path.read_text(encoding="utf-8")


def test_cli_leakage_synthetic_and_csv(tmp_path, capsys, synthetic_df):
    out = tmp_path / "syn"
    main(["leakage", "--synthetic", "--machines", "3", "--segments", "2", "--repeats", "1",
          "--models", "nearest_centroid", "--out", str(out)])  # fmt: skip
    text = capsys.readouterr().out
    assert "nearest_centroid" in text
    assert "inflation" in text
    md = (out / "leakage.md").read_text(encoding="utf-8")
    assert "severity 0.05-0.15" in md

    csv = tmp_path / "table.csv"
    synthetic_df.to_csv(csv, index=False)
    csv.with_suffix(".json").write_text(json.dumps({"dataset_id": "from-sidecar"}), "utf-8")
    main(["leakage", str(csv), "--models", "nearest_centroid", "--repeats", "1",
          "--out", str(tmp_path / "csv")])  # fmt: skip
    assert "from-sidecar" in (tmp_path / "csv" / "leakage.md").read_text(encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["leakage", "--out", str(tmp_path / "none")])
    assert exc.value.code == 2


def test_decision_rule_by_hand():
    def row(name, kind, point, low):
        return {
            "baseline": name,
            "kind": kind,
            "metrics": {"balanced_accuracy": point},
            "ci95": {"balanced_accuracy": (low, 1.0)},
        }

    rows = [
        row("majority_class", "baseline", 0.5, 0.5),
        row("envelope_rule", "baseline", 0.75, 0.6),
        row("good", "learned", 0.9, 0.8),
        row("close", "learned", 0.85, 0.7),
    ]
    d = decide_against_baselines(rows)
    assert d["good"]["beats_all_baselines"] is True
    assert d["close"]["beats_all_baselines"] is False
    assert d["close"]["versus"]["majority_class"]["meaningfully_better"] is True
    assert d["close"]["versus"]["envelope_rule"]["meaningfully_better"] is False
    # A tie with the baseline's point estimate is not "better".
    tie = decide_against_baselines([row("b", "baseline", 0.8, 0.7), row("m", "learned", 0.9, 0.8)])
    assert tie["m"]["beats_all_baselines"] is False
    # Without baselines nothing can be claimed.
    assert (
        decide_against_baselines([row("m", "learned", 0.9, 0.8)])["m"]["beats_all_baselines"]
        is False
    )
