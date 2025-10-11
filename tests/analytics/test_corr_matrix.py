import pandas as pd
import numpy as np
from src.analytics.corr_matrix import compute_correlations


def test_basic_corr_matrix():
    rng = np.random.default_rng(0)
    n = 64
    df = pd.DataFrame(
        {
            "x": rng.normal(size=n),
            "y": rng.normal(size=n),
            "z": rng.normal(size=n),
        }
    )
    rep = compute_correlations(df)
    assert set(rep.overall.columns) == {"x", "y", "z"}
    assert rep.overall.shape == (3, 3)
    assert rep.leakage is None


def test_leakage_detects_high_corr():
    rng = np.random.default_rng(1)
    n = 64
    x = rng.normal(size=n)
    target = x * 0.98 + rng.normal(scale=0.02, size=n)
    df = pd.DataFrame({"x": x, "target": target, "noise": rng.normal(size=n)})
    rep = compute_correlations(df, target_col="target", leakage_abs_threshold=0.95)
    assert rep.leakage is not None
    assert "x" in rep.leakage.index


def test_by_regime_works():
    rng = np.random.default_rng(2)
    n = 60
    df = pd.DataFrame(
        {
            "f1": rng.normal(size=n),
            "f2": rng.normal(size=n),
            "reg": np.repeat(["low", "high"], n // 2).tolist()
            + (["low"] if n % 2 else []),
        }
    )
    rep = compute_correlations(df, regime_col="reg")
    assert set(rep.by_regime.keys()) <= {"low", "high"}
