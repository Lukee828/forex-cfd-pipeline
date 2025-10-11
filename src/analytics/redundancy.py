from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Tuple


def redundancy_filter(
    df: pd.DataFrame, threshold: float = 0.9, method: str = "pearson"
) -> Tuple[List[str], List[str]]:
    """
    Drop highly correlated features using a simple greedy strategy.
    Returns (kept_columns, dropped_columns).
    """
    if df.empty:
        return [], []
    corr = df.corr(method=method).abs()
    # upper triangle without diagonal
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = set()
    kept = []
    for col in df.columns:
        # if col has any correlation > threshold with an already-kept column, drop it
        if any(upper.get(col, pd.Series()).reindex(kept).fillna(0) > threshold):
            to_drop.add(col)
        else:
            kept.append(col)
    return kept, [c for c in df.columns if c in to_drop]
