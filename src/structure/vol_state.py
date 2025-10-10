from __future__ import annotations
import numpy as np
import pandas as pd


def classify_vol_state(
    close: pd.Series,
    window: int = 20,
    pct_window: int = 100,
    low_q: float = 0.3,
    high_q: float = 0.7,
) -> pd.Series:
    """
    Classify volatility regime using Bollinger Bandwidth percentile.

    - BB width = (2 * rolling_std) / rolling_mean
    - Percentile of BB width over `pct_window`
    - Labels:
        < low_q  -> "low"
        > high_q -> "high"
        else     -> "neutral"
    """
    s = pd.Series(close).astype(float)
    if len(s) < max(window, pct_window):
        return pd.Series(["neutral"] * len(s), index=s.index)

    ma = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=0)
    bbw = (2.0 * sd) / ma.replace(0.0, np.nan)

    # rolling percentile via rank on a trailing window
    def _pct_rank(x: pd.Series) -> float:
        if x.isna().all():
            return np.nan
        last = x.iloc[-1]
        r = (x <= last).mean()
        return float(r)

    pct = bbw.rolling(pct_window, min_periods=pct_window).apply(_pct_rank, raw=False)

    out = pd.Series("neutral", index=s.index, dtype=object)
    out = out.mask(pct < low_q, "low")
    out = out.mask(pct > high_q, "high")
    return out
