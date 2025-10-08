from __future__ import annotations
import numpy as np
import pandas as pd

from ..base import Factor, FactorSpec, registry


class SMASlope(Factor):
    """
    Signal = sign of SMA(n) slope (SMA - SMA.shift(lookback)).
    +1 if slope > 0, -1 if slope < 0, 0 otherwise.
    Warm-up region (first n bars) returns NaN.
    """

    def __init__(self, n: int = 20, lookback: int = 1, name: str | None = None) -> None:
        super().__init__(name or f"sma_slope_{n}_{lookback}")
        self.n = int(n)
        self.lookback = int(lookback)

    def compute(self, df: "pd.DataFrame | pd.Series") -> pd.Series:
        # Normalize input to DataFrame with a 'close' column
        if isinstance(df, pd.Series):
            df = df.to_frame("close")
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame({"close": pd.Series(df)})

        if "close" not in df.columns:
            first_col = df.columns[0]
            if str(first_col) != "close":
                df = df.rename(columns={first_col: "close"})

        s = pd.to_numeric(df["close"], errors="coerce").astype(float)
        sma = s.rolling(self.n, min_periods=self.n).mean()
        slope = sma - sma.shift(self.lookback)

        out = pd.Series(np.nan, index=s.index)  # keep warm-up NaNs
        out[:] = 0.0
        out[slope > 0] = 1.0
        out[slope < 0] = -1.0
        out.name = f"sma_slope_{self.n}_{self.lookback}"
        return out


# Self-register a couple of useful presets

# --- Register common SMASlope specs with the global registry ---
try:
    _registered_sma_slope  # type: ignore[name-defined]
except NameError:
    _registered_sma_slope = True
    # You can add more specs here as needed
    registry.register(
        FactorSpec(name="sma_slope_20_1", factory=lambda: SMASlope(n=20, lookback=1))
    )
    registry.register(
        FactorSpec(name="sma_slope_50_1", factory=lambda: SMASlope(n=50, lookback=1))
    )

# --- Register SMASlope specs (guarded once) ---
try:
    _registered_sma_slope  # type: ignore[name-defined]
except NameError:
    _registered_sma_slope = True
    registry.register(
        FactorSpec(name="sma_slope_20_1", factory=lambda: SMASlope(n=20, lookback=1))
    )
    registry.register(
        FactorSpec(name="sma_slope_50_1", factory=lambda: SMASlope(n=50, lookback=1))
    )
