import pandas as pd
import pytest

from pumpguard.dataset import group_train_test_split, make_synthetic_dataset


@pytest.fixture(scope="module")
def small_df():
    return make_synthetic_dataset(
        conditions=("healthy", "imbalance", "bearing_outer"),
        machines_per_condition=4,
        segments_per_machine=2,
        duration=0.25,
        seed=11,
    )


def test_shape_and_labels(small_df):
    assert len(small_df) == 3 * 4 * 2
    assert small_df["group_id"].nunique() == 12
    assert set(small_df["condition"]) == {"healthy", "imbalance", "bearing_outer"}
    assert small_df["synthetic"].all()
    assert small_df["sample_id"].is_unique
    for col in ("rms", "kurtosis", "amp_1x", "env_bpfo_ratio"):
        assert col in small_df.columns


def test_healthy_rows_have_zero_severity(small_df):
    assert (small_df.loc[small_df["condition"] == "healthy", "severity"] == 0).all()
    assert (small_df.loc[small_df["condition"] != "healthy", "severity"] > 0).all()


def test_dataset_is_reproducible():
    kwargs = {
        "conditions": ("imbalance",),
        "machines_per_condition": 2,
        "segments_per_machine": 2,
        "duration": 0.2,
        "seed": 5,
    }
    first, second = make_synthetic_dataset(**kwargs), make_synthetic_dataset(**kwargs)
    pd.testing.assert_frame_equal(first, second)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"conditions": ("nope",)}, "conditions"),
        ({"conditions": ()}, "conditions"),
        ({"machines_per_condition": 0}, "machines_per_condition"),
        ({"rpm_range": (3000.0, 1000.0)}, "rpm_range"),
        ({"noise_range": (-1.0, 0.1)}, "noise_range"),
    ],
)
def test_invalid_arguments_raise(kwargs, message):
    with pytest.raises(ValueError, match=message):
        make_synthetic_dataset(**kwargs)


def test_group_split_has_no_leakage_and_keeps_all_classes(small_df):
    train, test = group_train_test_split(small_df, test_fraction=0.25, seed=0)
    assert set(train["group_id"]).isdisjoint(test["group_id"])
    assert len(train) + len(test) == len(small_df)
    assert set(train["condition"]) == set(test["condition"]) == set(small_df["condition"])


def test_group_split_without_stratification(small_df):
    train, test = group_train_test_split(small_df, test_fraction=0.5, stratify_col=None)
    assert set(train["group_id"]).isdisjoint(test["group_id"])
    assert test["group_id"].nunique() == 6


def test_group_split_validates_inputs(small_df):
    with pytest.raises(ValueError, match="test_fraction"):
        group_train_test_split(small_df, test_fraction=1.0)
    with pytest.raises(ValueError, match="group"):
        group_train_test_split(small_df, group_col="missing")
    with pytest.raises(ValueError, match="stratify"):
        group_train_test_split(small_df, stratify_col="missing")
    mixed = small_df.assign(group_id="one-group")
    with pytest.raises(ValueError, match="exactly one"):
        group_train_test_split(mixed)
