from __future__ import annotations
import pandas as pd


def fwd_return(close: pd.Series, horizon: int = 1) -> pd.Series:
    """
    Forward arithmetic return over `horizon` steps: close.shift(-h)/close - 1
    """
    c = pd.Series(close).astype("float64")
    return (c.shift(-horizon) / c) - 1.0
