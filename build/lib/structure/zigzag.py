from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class ZigZagParams:
    pct: float | None = None  # percentage threshold, e.g. 1.0 = 1%
    atr_n: int | None = None  # ATR window if ATR-based threshold
    atr_k: float | None = None  # multiplier for ATR threshold


def _threshold(series: pd.Series, p: ZigZagParams) -> pd.Series:
    if p.pct is not None:
        return (series.abs() * (p.pct / 100.0)).reindex(series.index)
    if p.atr_n and p.atr_k:
        atr = series.diff().abs().rolling(int(p.atr_n)).mean()
        return atr * float(p.atr_k)
    raise ValueError("Provide either pct or (atr_n, atr_k).")


def zigzag(close: pd.Series, params: ZigZagParams) -> pd.DataFrame:
    """Return pivots for a close series. Output: [timestamp, close, pivot]."""
    close = pd.Series(close).dropna()
    thr = _threshold(close, params)
    if len(close) < 3:
        return pd.DataFrame(
            {
                "timestamp": close.index,
                "close": close.values,
                "pivot": [False] * len(close),
            }
        )

    pivots = np.zeros(len(close), dtype=bool)
    last_price = close.iloc[0]
    direction = 0  # 0 unknown, +1 up leg, -1 down leg

    for i in range(1, len(close)):
        move = close.iloc[i] - last_price
        if direction >= 0:
            if move >= 0:
                if move >= thr.iloc[i]:  # continue up
                    direction = +1
                # else: still undecided
            else:
                if abs(move) >= thr.iloc[i]:  # reversal down
                    pivots[i] = True
                    last_price = close.iloc[i]
                    direction = -1
        else:
            if move <= 0:
                if abs(move) >= thr.iloc[i]:  # continue down
                    direction = -1
            else:
                if move >= thr.iloc[i]:  # reversal up
                    pivots[i] = True
                    last_price = close.iloc[i]
                    direction = +1

    out = pd.DataFrame(
        {"timestamp": close.index, "close": close.values, "pivot": pivots},
        index=close.index,
    )
    return out.reset_index(drop=True)
