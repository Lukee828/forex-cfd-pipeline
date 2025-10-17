from dataclasses import dataclass
from typing import Optional
import os
import re
import numpy as np
import pandas as pd

@dataclass
class BarSpec:
    symbol: str
    timeframe: str  # e.g. "H1","M1","D1"
    start: str
    end: str

def _to_pandas_freq(tf: str) -> str:
    t = (tf or "").upper().strip()
    mapping = {"M1":"1min","M5":"5min","M15":"15min","M30":"30min","H1":"1h","H4":"4h","D1":"1D"}
    if t in mapping:
        return mapping[t]
    m = re.fullmatch(r"([MHD])(\d+)", t)
    if m:
        unit, num = m.group(1), m.group(2)
        if unit == "M":
            return f"{num}min"
        elif unit == "H":
            return f"{num}h"
        else:
            return f"{num}D"
    return t

def _offline_bars(spec: BarSpec) -> pd.DataFrame:
    freq = _to_pandas_freq(spec.timeframe)
    idx = pd.date_range(spec.start, spec.end, freq=freq, inclusive="left")
    rng = np.random.default_rng(42)
    price = 1.10 + np.cumsum(rng.normal(0.0, 0.0005, len(idx)))
    df = pd.DataFrame({
        "open":  price,
        "high":  price,
        "low":   price,
        "close": price,
        "volume": np.ones(len(idx), dtype=float)
    }, index=idx)
    df.index.name = "ts"
    return df

def get_bars(spec: BarSpec) -> pd.DataFrame:
    if os.environ.get("DUKASCOPY_OFFLINE") == "1":
        return _offline_bars(spec)
    # TODO: real Dukascopy download; for now, use offline for smoke
    return _offline_bars(spec)
