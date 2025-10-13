# src/analytics/corr_matrix.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd


@dataclass
class RedundancyReport:
    threshold: float
    dropped_pairs: List[Tuple[str, str, float]]  # (col_i, col_j, corr)
    kept_columns: List[str]


def _numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    # Keep only numeric columns; drop all-NaN cols
    num = df.select_dtypes(include=[np.number]).copy()
    return num.loc[:, num.columns[num.notna().any(axis=0)]]


def corr_matrix(df: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    """Compute correlation matrix for numeric columns only."""
    return _numeric_df(df).corr(method=method)


def find_redundant_pairs(
    corr: pd.DataFrame, threshold: float = 0.97
) -> List[Tuple[str, str, float]]:
    """
    Return (col_i, col_j, abs_corr) for abs(corr) > threshold over the upper triangle.
    """
    pairs: List[Tuple[str, str, float]] = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            c = corr.iloc[i, j]
            if pd.notna(c) and abs(c) > threshold:
                pairs.append((cols[i], cols[j], float(abs(c))))
    # Sort strongest first for deterministic behavior
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def drop_redundant(
    df: pd.DataFrame, threshold: float = 0.97
) -> Tuple[pd.DataFrame, RedundancyReport]:
    """
    Greedy, stable redundancy drop: for each pair above threshold, drop the second column
    if both are still present. Deterministic and fast.
    """
    num = _numeric_df(df)
    if num.shape[1] <= 1:
        return num.copy(), RedundancyReport(threshold, [], list(num.columns))

    corr = num.corr()
    pairs = find_redundant_pairs(corr, threshold)

    kept = list(num.columns)
    dropped_pairs: List[Tuple[str, str, float]] = []
    present = set(kept)
    for a, b, c in pairs:
        if a in present and b in present:
            # Drop b, keep a (stable preference for left-most / earlier col)
            present.remove(b)
            dropped_pairs.append((a, b, c))

    reduced = num.loc[:, [c for c in kept if c in present]].copy()
    report = RedundancyReport(
        threshold=threshold,
        dropped_pairs=dropped_pairs,
        kept_columns=list(reduced.columns),
    )
    return reduced, report


def per_regime_corr(
    df: pd.DataFrame, regime_col: str = "regime", method: str = "pearson"
) -> Dict[str, pd.DataFrame]:
    """
    If regime column exists, compute correlation matrix per regime; else return {"all": corr(df)}.
    """
    if regime_col in df.columns:
        out: Dict[str, pd.DataFrame] = {}
        for key, part in df.groupby(regime_col):
            out[str(key)] = corr_matrix(part, method=method)
        return out
    return {"all": corr_matrix(df, method=method)}
