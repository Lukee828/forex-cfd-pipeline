# tests/analytics/test_corr_matrix.py
import numpy as np
import pandas as pd

from src.analytics.corr_matrix import (
    corr_matrix,
    find_redundant_pairs,
    drop_redundant,
    per_regime_corr,
)


def test_drop_redundant_pairs_basic():
    rng = np.random.default_rng(42)
    n = 200
    a = rng.normal(size=n)
    b = a + rng.normal(scale=1e-3, size=n)  # ~perfectly correlated with a
    c = rng.normal(size=n)
    df = pd.DataFrame({"a": a, "b": b, "c": c})

    corr = corr_matrix(df)
    pairs = find_redundant_pairs(corr, threshold=0.97)
    assert any({tuple(sorted((i, j))) for i, j, _ in pairs} & {("a", "b")})

    reduced, report = drop_redundant(df, threshold=0.97)
    # one of (a,b) is dropped, c remains
    assert set(reduced.columns) in ({"a", "c"}, {"b", "c"})
    # report reflects action
    assert report.dropped_pairs and any({"a", "b"} == set(p[:2]) for p in report.dropped_pairs)


def test_per_regime_corr_shapes():
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame(
        {
            "regime": ["low"] * (n // 2) + ["high"] * (n - n // 2),
            "x": rng.normal(size=n),
            "y": rng.normal(size=n),
            "z": rng.normal(size=n),
        }
    )
    out = per_regime_corr(df)
    assert set(out.keys()) == {"low", "high"}
    for k, cm in out.items():
        assert set(cm.columns) == {"x", "y", "z"}
        assert cm.shape == (3, 3)
