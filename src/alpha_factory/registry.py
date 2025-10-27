from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


# ---------- helpers ----------
def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def _rsi(s: pd.Series, n: int) -> pd.Series:
    # classic Wilder RSI
    delta = s.diff()
    up = delta.clip(lower=0.0)
    dn = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = roll_up / (roll_dn.replace({0.0: np.nan}))
    rsi = 100 - 100 / (1 + rs)
    return rsi


# ---------- factor objects ----------
@dataclass
class _SmaCross:
    fast: int
    slow: int

    @property
    def name(self) -> str:
        return f"sma_cross_{self.fast}_{self.slow}"

    def compute(self, s: pd.Series) -> pd.Series:
        f = _sma(s, self.fast)
        slow_ma = _sma(s, self.slow)
        sig = np.where(f > slow_ma, 1.0, -1.0).astype(float)
        out = pd.Series(sig, index=s.index, name=self.name)
        out.iloc[: max(self.fast, self.slow) - 1] = 0.0  # no warm-up NaN
        return out


@dataclass
class _RsiThresh:
    n: int
    lo: float
    hi: float

    @property
    def name(self) -> str:
        return f"rsi_thresh_{self.n}_{int(self.lo)}_{int(self.hi)}"

    def compute(self, s: pd.Series) -> pd.Series:
        r = _rsi(s, self.n)
        sig = np.full(len(s), 0.0, dtype=float)
        sig[r < self.lo] = 1.0
        sig[r > self.hi] = -1.0
        out = pd.Series(sig, index=s.index, name=self.name)
        return out


@dataclass
class _SmaSlope:
    window: int
    lookback: int

    @property
    def name(self) -> str:
        return f"sma_slope_{self.window}_{self.lookback}"

    def compute(self, s: pd.Series) -> pd.Series:
        m = _sma(s, self.window)
        slope = m.diff(self.lookback)
        sig = np.sign(slope).fillna(0.0).astype(float)
        out = pd.Series(sig, index=s.index, name=self.name)
        # ensure no warm-up NaNs
        warm = max(self.window, self.lookback + 1) - 1
        if warm > 0:
            out.iloc[:warm] = 0.0
        return out


# ---------- public API ----------
def make(name: str):
    """
    Known patterns:
      - sma_cross_<fast>_<slow>
      - rsi_thresh_<n>_<lo>_<hi>
      - sma_slope_<window>_<lookback>
    """
    parts = name.split("_")
    if name.startswith("sma_cross_") and len(parts) == 4:
        return _SmaCross(fast=int(parts[2]), slow=int(parts[3]))
    if name.startswith("rsi_thresh_") and len(parts) == 5:
        return _RsiThresh(n=int(parts[2]), lo=float(parts[3]), hi=float(parts[4]))
    if name.startswith("sma_slope_") and len(parts) == 4:
        return _SmaSlope(window=int(parts[2]), lookback=int(parts[3]))
    raise ValueError(f"Unknown factor: {name}")


def names() -> list[str]:
    # keep this in sync with tests’ expected examples
    return ["sma_cross_10_30", "rsi_thresh_14_30_70", "sma_slope_20_1"]
