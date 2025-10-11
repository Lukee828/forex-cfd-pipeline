import pandas as pd
from src.analytics.redundancy import redundancy_filter


def test_redundancy_filter_basic():
    # Create correlated columns: b ~= a, d ~= c; e is independent
    a = pd.Series(range(100), dtype=float)
    b = a + 0.0001
    c = pd.Series(range(100, 200), dtype=float)
    d = c * 1.0
    e = pd.Series(range(100, 200))[::-1].reset_index(
        drop=True
    )  # not perfectly correlated with a or c
    df = pd.DataFrame({"a": a, "b": b, "c": c, "d": d, "e": e})
    kept, dropped = redundancy_filter(df, threshold=0.95)
    # Should drop one from {a,b} and one from {c,d}; keep e
    assert "e" in kept
    assert len(dropped) == 2
    assert set(kept).union(dropped) == set(df.columns)
