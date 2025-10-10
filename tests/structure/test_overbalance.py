import pandas as pd
from structure.overbalance import overbalance


def test_overbalance_basic():
    # Build simple pivots alternating up/down with growing magnitude
    ts = pd.date_range("2024-01-01", periods=7, freq="h")
    close = [100, 110, 105, 120, 115, 140, 130]  # swings: 10,5,15,5,25,10
    pivot = [False, True, True, True, True, True, True]  # mark pivots for simplicity
    piv = pd.DataFrame({"timestamp": ts, "close": close, "pivot": pivot})
    ob = overbalance(piv, lookback=2)
    assert "overbalanced" in ob.columns
    # Expect later large moves to be flagged at their ending pivot
    assert ob["overbalanced"].sum() >= 1
