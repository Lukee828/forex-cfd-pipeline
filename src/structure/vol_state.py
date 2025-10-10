from __future__ import annotations
import pandas as pd


def classify_vol_state(close: pd.Series, window: int = 14) -> pd.Series:
    """
    Placeholder: return simple 'neutral' labels. Replace with
    ADX/Bollinger width percentile, etc.
    """
    return pd.Series(["neutral"] * len(close), index=close.index)
