from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

from structure.zigzag import zigzag, ZigZagParams
from structure.overbalance import overbalance
from structure.vol_state import classify_vol_state


@dataclass
class StructureConfig:
    # zigzag
    pct: float | None = 1.0
    atr_n: int | None = None
    atr_k: float | None = None
    # vol-state
    bbw_window: int = 20
    bbw_pct_window: int = 252


def build_structure_features(
    prices: pd.DataFrame,
    cfg: StructureConfig | None = None,
) -> pd.DataFrame:
    """
    Input: prices with columns ['timestamp','close'] (timestamp tz-naive UTC).
    Output columns:
      - timestamp
      - close
      - pivot (bool)
      - swing (float)  # absolute move between consecutive pivots (NaN if none yet)
      - vol_state (str)  # e.g., 'low', 'neutral', 'high'
    """
    if cfg is None:
        cfg = StructureConfig()

    # basic checks
    for col in ("timestamp", "close"):
        if col not in prices.columns:
            raise ValueError("prices must include columns: timestamp, close")

    df = prices.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    # ZigZag
    zz_params = ZigZagParams(pct=cfg.pct, atr_n=cfg.atr_n, atr_k=cfg.atr_k)
    piv = zigzag(df.set_index("timestamp")["close"], zz_params)
    piv = piv.rename(columns={"timestamp": "ts_zz"})
    # Merge back on position (both DataFrames are sorted identically)
    df["pivot"] = piv["pivot"].astype(bool).values

    # Swing sizes measured between pivot points (absolute)
    swing = [float("nan")] * len(df)
    last_pivot_idx = None
    last_pivot_close = None
    for i, (is_pv, c) in enumerate(zip(df["pivot"].tolist(), df["close"].tolist())):
        if is_pv or i == 0:
            if last_pivot_idx is not None:
                swing[i] = abs(c - last_pivot_close)
            last_pivot_idx = i
            last_pivot_close = c
    df["swing"] = pd.Series(swing, index=df.index)

    # Overbalance (flags at row-level, aligned by index)
    ob = overbalance(
        pd.DataFrame({"timestamp": df["timestamp"], "close": df["close"], "pivot": df["pivot"]}),
        lookback=5,
    )
    # not strictly needed for the minimal feature set, but often useful downstream
    if "overbalanced" in ob.columns:
        df["overbalanced"] = ob["overbalanced"].astype(bool).values

    # Volatility state as labels
    df = df.set_index("timestamp")
    vol = classify_vol_state(
        df["close"],
        window=cfg.bbw_window,  # bbw calc uses its own pct window internally
    )
    df["vol_state"] = vol.astype(str)
    return df.reset_index()
