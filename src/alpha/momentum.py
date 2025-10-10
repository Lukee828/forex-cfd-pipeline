from __future__ import annotations
import pandas as pd


def roc(close: pd.Series, n: int = 5) -> pd.Series:
    """
    Rate-of-change percentage: (close / close.shift(n) - 1) * 100
    NaNs preserved at the start.
    """
    c = pd.Series(close).astype("float64")
    return (c / c.shift(n) - 1.0) * 100.0
