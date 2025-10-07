from __future__ import annotations
import pandas as pd
from dataclasses import dataclass
from ..base import Factor


@dataclass
class SmaCross(Factor):
    name: str = "sma_cross_10_30"
    requires = ("close",)
    fast: int = 10
    slow: int = 30

    def compute(self, df: pd.DataFrame) -> pd.Series:
        import pandas as pd

        # [alpha-factory] robust, idempotent input normalization
        # Accept Series, DataFrame, or array-like; ensure a 'close' column
        if isinstance(df, pd.Series):
            df = df.to_frame(name="close")
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame({"close": pd.Series(df)})

        if "close" not in df.columns:
            # rename first column to 'close' if needed
            first_col = df.columns[0]
            if str(first_col) != "close":
                df = df.rename(columns={first_col: "close"})

        s = pd.to_numeric(df["close"], errors="coerce").astype(float)

        # rolling means with warm-up NaNs preserved
        fast = s.rolling(self.fast, min_periods=self.fast).mean()
        slow = s.rolling(self.slow, min_periods=self.slow).mean()

        # signal only where slow is defined; keep early NaNs
        sig = pd.Series(index=s.index, dtype=float)
        m = slow.notna()
        sig[m] = (fast[m] > slow[m]).astype(float) - (fast[m] < slow[m]).astype(float)
        return sig


# --- Register common SMACross specs with the global registry ---
try:
    _registered_sma_cross  # type: ignore[name-defined]
except NameError:
    from ..base import FactorSpec, registry

    registry.register(
        FactorSpec(
            name="sma_cross_10_30",
            factory=lambda: SMACross(n_fast=10, n_slow=30),
        )
    )
    _registered_sma_cross = True

# --- Back-compat alias (registry uses SMACross) ---
try:
    SMACross  # type: ignore[name-defined]
except NameError:
    SMACross = SmaCross
