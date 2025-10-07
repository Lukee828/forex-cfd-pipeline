from __future__ import annotations
import numpy as np
import pandas as pd

from ..base import Factor, FactorSpec
from ..base import registry


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    gain = up.ewm(alpha=1 / n, adjust=False).mean()
    loss = down.ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi.iloc[:n] = np.nan  # warm-up
    return rsi


class RSIThreshold(Factor):
    """
    Signal:
      +1 when RSI < lo (oversold),
       0 when lo <= RSI <= hi,
      -1 when RSI > hi (overbought).
    Warm-up (first n) returns NaN.
    """

    def __init__(
        self, n: int = 14, lo: float = 30, hi: float = 70, name: str | None = None
    ) -> None:
        super().__init__(name or f"rsi_thresh_{n}_{int(lo)}_{int(hi)}")
        self.n = int(n)
        self.lo = float(lo)
        self.hi = float(hi)

    def compute(self, df: pd.DataFrame) -> pd.Series:
        s = df.iloc[:, 0].astype(float)
        r = _rsi(s, self.n)
        out = pd.Series(np.nan, index=s.index)
        out.loc[r < self.lo] = 1
        out.loc[(r >= self.lo) & (r <= self.hi)] = 0
        out.loc[r > self.hi] = -1
        return out


# Self-register common preset
registry.register(
    FactorSpec(
        name="rsi_thresh_14_30_70", factory=lambda: RSIThreshold(n=14, lo=30, hi=70)
    )
)
try:
    _registered_rsi_thresh  # type: ignore[name-defined]
except NameError:
    _registered_rsi_thresh = True
    # registrations live in module scope via registry.register(FactorSpec(...)) above
