import numpy as np
import pandas as pd
import pytest

from pumpguard.baselines import (
    EnvelopeRule,
    MajorityClass,
    NearestCentroid,
    SingleFeatureThreshold,
    best_threshold,
)


def test_best_threshold_both_directions():
    values = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    t, d, score = best_threshold(values, [0, 0, 0, 1, 1, 1])
    assert d == 1
    assert 3.0 < t < 10.0
    assert score == 1.0
    t, d, score = best_threshold(values, [1, 1, 1, 0, 0, 0])
    assert d == -1
    assert 3.0 < t < 10.0
    assert score == 1.0


def test_best_threshold_needs_two_classes():
    with pytest.raises(ValueError, match="both classes"):
        best_threshold([1.0, 2.0], [1, 1])


def test_best_threshold_caps_candidates_on_large_input():
    rng = np.random.default_rng(0)
    values = np.concatenate([rng.normal(0, 1, 5000), rng.normal(4, 1, 5000)])
    _, d, score = best_threshold(values, np.repeat([0, 1], 5000))
    assert d == 1
    assert score > 0.95


def test_majority_class_tie_break_is_deterministic():
    m = MajorityClass().fit(pd.DataFrame(index=range(4)), ["b", "a", "a", "b"])
    assert m.describe() == "always predicts 'a'"
    assert list(m.predict(pd.DataFrame(index=range(2)))) == ["a", "a"]
    with pytest.raises(ValueError, match="zero samples"):
        MajorityClass().fit(pd.DataFrame(), [])


def _toy():
    X = pd.DataFrame(
        {
            "noise": [0.3, 0.1, 0.4, 0.2, 0.35, 0.15],
            "kurtosis": [3.0, 3.1, 2.9, 6.0, 7.0, 6.5],
            "env_bpfo_ratio": [2.0, 2.2, 1.9, 40.0, 2.5, 2.1],
            "env_bpfi_ratio": [2.1, 1.8, 2.3, 2.0, 30.0, 25.0],
        }
    )
    y = np.array(["healthy", "healthy", "healthy", "outer", "inner", "inner"], dtype=object)
    return X, y


def test_single_feature_threshold_picks_the_informative_feature():
    X, y = _toy()
    y_det = np.where(y == "healthy", "healthy", "damaged")
    model = SingleFeatureThreshold(["noise", "kurtosis"]).fit(X, y_det)
    assert model.feature_ == "kurtosis"
    assert list(model.predict(X)) == list(y_det)
    assert "kurtosis >" in model.describe()


def test_single_feature_threshold_validates():
    X, y = _toy()
    with pytest.raises(ValueError, match="labels must be"):
        SingleFeatureThreshold(["kurtosis"]).fit(X, y)
    with pytest.raises(RuntimeError, match="fit"):
        SingleFeatureThreshold(["kurtosis"]).predict(X)
    with pytest.raises(ValueError, match="at least one"):
        SingleFeatureThreshold([])
    with pytest.raises(ValueError, match="missing feature"):
        SingleFeatureThreshold(["absent"]).fit(X, np.where(y == "healthy", "healthy", "damaged"))


def test_envelope_rule_diagnosis_and_detection():
    X, y = _toy()
    diag = EnvelopeRule().fit(X, y)
    assert list(diag.predict(X)) == list(y)
    assert "outer if BPFO" in diag.describe()
    det = EnvelopeRule("detection").fit(X, np.where(y == "healthy", "healthy", "damaged"))
    assert list(det.predict(X)) == ["healthy"] * 3 + ["damaged"] * 3


def test_envelope_rule_refuses_inverted_physics():
    X, y = _toy()
    X = X.assign(env_bpfo_ratio=-X["env_bpfo_ratio"], env_bpfi_ratio=-X["env_bpfi_ratio"])
    model = EnvelopeRule().fit(X, y)
    assert set(model.predict(X)) == {"healthy"}


def test_envelope_rule_validates():
    X, y = _toy()
    with pytest.raises(ValueError, match="mode"):
        EnvelopeRule("other")
    with pytest.raises(ValueError, match="subset"):
        EnvelopeRule().fit(X, np.array(["healthy", "x", "x", "x", "x", "x"]))
    with pytest.raises(RuntimeError, match="fit"):
        EnvelopeRule().predict(X)
    with pytest.raises(ValueError, match="non-finite"):
        EnvelopeRule().fit(X.assign(env_bpfo_ratio=np.nan), y)


def test_nearest_centroid_uses_training_statistics_only():
    X, y = _toy()
    model = NearestCentroid(["kurtosis", "env_bpfo_ratio", "env_bpfi_ratio"]).fit(X, y)
    assert list(model.predict(X)) == list(y)
    assert model.describe().startswith("nearest of 3 class means")
    shifted = X.assign(kurtosis=X["kurtosis"] + 100)  # predict must not refit scaling
    assert set(model.predict(shifted)) != set(y)


def test_nearest_centroid_validates():
    X, y = _toy()
    assert NearestCentroid(["kurtosis"]).describe() == "unfitted"
    with pytest.raises(RuntimeError, match="fit"):
        NearestCentroid(["kurtosis"]).predict(X)
    with pytest.raises(ValueError, match="at least one"):
        NearestCentroid([])
    with pytest.raises(ValueError, match="equally long"):
        NearestCentroid(["kurtosis"]).fit(X, y[:2])
