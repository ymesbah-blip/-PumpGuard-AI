import json

import numpy as np
import pandas as pd
import pytest

from paderborn_fixtures import FIXTURE_DURATION_S, write_dataset
from pumpguard.benchmark import (
    DEFAULT_FEATURES,
    run_benchmark,
    synthetic_feature_table,
    write_report,
)
from pumpguard.cli import main
from pumpguard.datasets.paderborn import TASKS


@pytest.fixture(scope="module")
def synthetic_df():
    return synthetic_feature_table(seed=0, machines=4, segments=3)


def test_synthetic_benchmark_structure(synthetic_df):
    r = run_benchmark(synthetic_df, n_boot=100)
    assert r["protocol"] == "stratified_group_kfold"
    assert set(r["tasks"]) == {"detection", "diagnosis"}
    names = [x["baseline"] for x in r["tasks"]["diagnosis"]]
    assert names == ["majority_class", "envelope_rule", "nearest_centroid"]
    for task in r["tasks"].values():
        for res in task:
            lo, hi = res["ci95"]["balanced_accuracy"]
            assert lo <= res["metrics"]["balanced_accuracy"] <= hi
            assert len(res["fitted_rules"]) == r["protocol_info"]["n_splits"]
    majority = r["tasks"]["detection"][0]["metrics"]["balanced_accuracy"]
    assert majority == pytest.approx(0.5)
    assert "detection/envelope_rule" in r["leakage_check"]


def test_every_group_is_predicted_by_a_model_that_never_saw_it(synthetic_df):
    r = run_benchmark(synthetic_df, n_boot=10)
    groups_reported = {g["group"] for g in r["tasks"]["diagnosis"][1]["per_group"]}
    assert groups_reported == set(synthetic_df["group_id"])


def test_predefined_split_is_respected_and_checked(synthetic_df):
    df = synthetic_df.copy()
    test_groups = {"healthy-m00", "bearing_outer-m00", "bearing_inner-m00"}
    df["split"] = np.where(df["group_id"].isin(test_groups), "test", "train")
    r = run_benchmark(df, n_boot=10)
    assert r["protocol"] == "predefined_split"
    assert set(r["protocol_info"]["test_groups"]) == test_groups
    assert "leakage_check" not in r
    first_train_row = df.index[df["split"] == "train"][0]
    df.loc[first_train_row, "split"] = "test"  # moves part of a training group to test
    with pytest.raises(ValueError, match="both sides"):
        run_benchmark(df, n_boot=10)
    with pytest.raises(ValueError, match="both 'train' and 'test'"):
        run_benchmark(df.assign(split="train"), n_boot=10)


def test_benchmark_input_validation(synthetic_df):
    with pytest.raises(ValueError, match="missing column"):
        run_benchmark(synthetic_df.drop(columns=["kurtosis"]))
    with pytest.raises(ValueError, match="healthy"):
        run_benchmark(synthetic_df[synthetic_df["label"] != "healthy"], n_boot=10)
    with pytest.raises(ValueError, match="finite"):
        run_benchmark(synthetic_df.assign(kurtosis=np.nan))


def test_nonfinite_rows_are_dropped_and_counted(synthetic_df):
    df = synthetic_df.copy()
    df.loc[df.index[:2], "kurtosis"] = np.nan
    assert run_benchmark(df, n_boot=10)["n_rows_dropped_nonfinite"] == 2


def test_diagnosis_skipped_for_other_label_sets(synthetic_df):
    df = synthetic_df[synthetic_df["label"] != "inner"]
    r = run_benchmark(df, n_boot=10)
    assert "diagnosis" not in r["tasks"]
    assert "not evaluated" in r["diagnosis_skipped"]


def test_report_files(tmp_path, synthetic_df):
    r = run_benchmark(synthetic_df, n_boot=20)
    json_path, md_path = write_report(
        r, tmp_path, {"dataset_id": "synthetic", "task": "dry-run", "synthetic": True}
    )
    payload = json.loads(json_path.read_text())
    assert payload["results"]["features"] == list(DEFAULT_FEATURES)
    md = md_path.read_text()
    for section in ("## Data", "## Protocol", "## Results: detection", "## Leakage check",
                    "## Limitations", "Synthetic data"):  # fmt: skip
        assert section in md


# ------------------------------------------------------- end-to-end via the CLI


def test_cli_paderborn_pipeline_on_fixtures(tmp_path, capsys):
    root = tmp_path / "pu"
    write_dataset(root, sorted(TASKS["real3"].bearings), measurements=1)
    d = str(FIXTURE_DURATION_S)

    assert main(["paderborn", "index", str(root), "--out", str(tmp_path / "idx.csv")]) == 0
    out = capsys.readouterr().out
    assert "CC BY-NC 4.0" in out
    assert "task real3" in out
    assert "complete" in out
    assert len(pd.read_csv(tmp_path / "idx.csv")) == 15

    some_file = next(root.rglob("*.mat"))
    assert main(["paderborn", "inspect", str(some_file)]) == 0
    assert "vibration_1" in capsys.readouterr().out

    feats = tmp_path / "feats.csv"
    assert main(["paderborn", "features", str(root), "--out", str(feats),
                 "--segment-seconds", str(FIXTURE_DURATION_S / 2),
                 "--expected-duration", d]) == 0  # fmt: skip
    assert feats.with_suffix(".json").exists()
    capsys.readouterr()

    assert main(["benchmark", str(feats), "--out", str(tmp_path / "bench"),
                 "--n-boot", "50"]) == 0  # fmt: skip
    out = capsys.readouterr().out
    assert "envelope_rule" in out
    report = (tmp_path / "bench" / "report.md").read_text()
    assert "not** validate" in report
    assert "CC BY-NC 4.0" in report


def test_cli_benchmark_synthetic_and_errors(tmp_path, capsys):
    assert main(["benchmark", "--synthetic", "--out", str(tmp_path), "--n-boot", "20"]) == 0
    assert "Synthetic data" in (tmp_path / "report.md").read_text()
    with pytest.raises(SystemExit) as exc:
        main(["benchmark"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        main(["paderborn", "index", str(tmp_path / "missing")])
