from __future__ import annotations
import pandas as pd


def overbalance(pivots: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """
    Placeholder: mark overbalance when last swing magnitude exceeds
    rolling max of prior swings (to be implemented).
    """
    return pd.DataFrame({"overbalanced": [False] * len(pivots)})
