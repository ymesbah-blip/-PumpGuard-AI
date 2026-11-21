import numpy as np
import pytest

from pumpguard.evaluation import (
    classification_metrics,
    confusion_matrix,
    group_bootstrap_ci,
    random_kfold,
    stratified_group_kfold,
)


def test_confusion_matrix_by_hand():
    cm = confusion_matrix(["a", "a", "b", "b", "b"], ["a", "b", "b", "b", "a"], ["a", "b"])
    np.testing.assert_array_equal(cm, [[1, 1], [1, 2]])


def test_confusion_matrix_rejects_unknown_labels():
    with pytest.raises(ValueError, match="not in labels"):
        confusion_matrix(["a"], ["c"], ["a", "b"])
    with pytest.raises(ValueError, match="same length"):
        confusion_matrix(["a"], ["a", "b"], ["a", "b"])


def test_metrics_by_hand():
    # true: 3 healthy, 1 outer; predicted: one healthy mistaken for outer
    m = classification_metrics(["h", "h", "h", "o"], ["h", "h", "o", "o"], ["h", "o"])
    assert m["accuracy"] == pytest.approx(0.75)
    assert m["per_class"]["h"] == pytest.approx(
        {"precision": 1.0, "recall": 2 / 3, "f1": 0.8, "support": 3}
    )
    assert m["per_class"]["o"]["precision"] == pytest.approx(0.5)
    assert m["balanced_accuracy"] == pytest.approx((2 / 3 + 1.0) / 2)
    assert m["macro_f1"] == pytest.approx((0.8 + 2 / 3) / 2)


def test_never_predicted_class_has_zero_precision():
    m = classification_metrics(["a", "b"], ["a", "a"], ["a", "b"])
    assert m["per_class"]["b"]["precision"] == 0.0
    with pytest.raises(ValueError, match="zero samples"):
        classification_metrics([], [])


def _toy_groups():
    groups = np.repeat([f"g{i}" for i in range(9)], 4)
    labels = np.repeat(["h", "h", "h", "o", "o", "o", "i", "i", "i"], 4)
    return groups, labels


def test_group_kfold_never_splits_a_group_and_tests_each_once():
    groups, labels = _toy_groups()
    folds = stratified_group_kfold(groups, labels, n_splits=3, seed=1)
    tested = []
    for train, test in folds:
        assert set(groups[train]).isdisjoint(groups[test])
        assert set(labels[test]) == {"h", "o", "i"}  # stratified: one group per class
        tested.extend(set(groups[test]))
    assert sorted(tested) == sorted(set(groups))


def test_group_kfold_validates():
    groups, labels = _toy_groups()
    with pytest.raises(ValueError, match="n_splits"):
        stratified_group_kfold(groups, labels, n_splits=10)
    labels[0] = "o"
    with pytest.raises(ValueError, match="more than one label"):
        stratified_group_kfold(groups, labels, n_splits=3)


def test_random_kfold_does_leak_groups():
    groups, _ = _toy_groups()
    folds = random_kfold(len(groups), n_splits=3, seed=0)
    assert sum(len(test) for _, test in folds) == len(groups)
    assert any(set(groups[tr]) & set(groups[te]) for tr, te in folds)
    with pytest.raises(ValueError, match="n_splits"):
        random_kfold(3, n_splits=5)


def _acc(t, p):
    return float(np.mean(t == p))


def test_group_bootstrap_ci_brackets_estimate_and_is_reproducible():
    groups, labels = _toy_groups()
    pred = labels.copy()
    pred[:4] = "o"  # one whole group wrong
    ci1 = group_bootstrap_ci(labels, pred, groups, _acc, n_boot=500, seed=3)
    ci2 = group_bootstrap_ci(labels, pred, groups, _acc, n_boot=500, seed=3)
    assert ci1 == ci2
    assert ci1[0] <= _acc(labels, pred) <= ci1[1]
    assert ci1[1] - ci1[0] > 0.05  # few groups -> visibly wide


def test_bootstrap_with_perfect_predictions_is_degenerate():
    groups, labels = _toy_groups()
    assert group_bootstrap_ci(labels, labels, groups, _acc, n_boot=50) == (1.0, 1.0)


def test_bootstrap_validates():
    with pytest.raises(ValueError, match="equally long"):
        group_bootstrap_ci(["a"], ["a", "b"], ["g"], _acc)
    with pytest.raises(ValueError, match="alpha"):
        group_bootstrap_ci(["a"], ["a"], ["g"], _acc, alpha=2)
