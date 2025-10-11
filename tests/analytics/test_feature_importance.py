import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from src.analytics.feature_importance import compute_permutation_importance


def test_feature_importance_basic():
    rng = np.random.default_rng(0)
    n = 200
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    # x1 drives label; x2 noise
    y = (x1 + 0.1 * rng.normal(size=n) > 0).astype(int)
    X = pd.DataFrame({"x1": x1, "x2": x2})
    clf = LogisticRegression(max_iter=200)
    imp = compute_permutation_importance(
        X, pd.Series(y), clf, n_splits=3, scoring="roc_auc"
    )
    # x1 should rank above x2
    assert imp.iloc[0]["feature"] == "x1"
