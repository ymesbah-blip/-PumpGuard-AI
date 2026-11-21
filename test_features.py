import numpy as np
from pumpguard.features import extract_features


def test_features_basic():
    x = np.array([-1.0, 0.0, 1.0, 0.0])
    f = extract_features(x)
    assert f["rms"] > 0
    assert f["peak"] == 1.0
    assert f["crest_factor"] >= 1.0
