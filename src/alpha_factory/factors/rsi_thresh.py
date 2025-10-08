from __future__ import annotations
import numpy as np
import pandas as pd

from ..base import Factor


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

    def compute(self, df):

        import numpy as np

        import pandas as pd

        # Normalize input to a DataFrame with a 'close' column (float)

        if isinstance(df, pd.Series):

            s = pd.to_numeric(df, errors="coerce").astype(float)

            df = pd.DataFrame({"close": s})

        elif isinstance(df, pd.DataFrame):

            if "close" not in df.columns:

                first = df.columns[0]

                df = df.rename(columns={first: "close"})

            df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)

        else:

            df = pd.DataFrame(
                {"close": pd.to_numeric(pd.Series(df), errors="coerce").astype(float)}
            )

        s = df["close"]

        # RSI via Wilder's smoothing

        delta = s.diff()

        up = delta.clip(lower=0)

        down = (-delta).clip(lower=0)

        roll_up = up.ewm(alpha=1 / self.n, adjust=False, min_periods=1).mean()

        roll_down = down.ewm(alpha=1 / self.n, adjust=False, min_periods=1).mean()

        rs = roll_up / roll_down.replace(0, np.nan)

        rsi = 100 - (100 / (1 + rs))

        # Signals: > hi => 1, < lo => -1, else 0. Fill NaNs to 0.

        sig = pd.Series(0.0, index=s.index)

        sig[rsi > self.hi] = 1.0

        sig[rsi < self.lo] = -1.0

        sig = sig.fillna(0.0)

        sig.name = f"rsi_thresh_{int(self.n)}_{float(self.lo)}_{float(self.hi)}"

        return sig


# --- Register common RSIThreshold specs with the global registry ---
try:
    _registered_rsi_thresh  # type: ignore[name-defined]
except NameError:
    _registered_rsi_thresh = True
    try:
        from ..base import FactorSpec, registry

        registry.register(
            FactorSpec(
                name="rsi_thresh_14_30_70",
                factory=lambda: RSIThreshold(n=14, lo=30, hi=70),
            )
        )
    except Exception:
        pass
