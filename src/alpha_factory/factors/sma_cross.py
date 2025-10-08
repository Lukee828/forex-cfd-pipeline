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

    def compute(self, df):

        # Normalize input

        if isinstance(df, pd.Series):

            s = pd.to_numeric(df, errors="coerce").astype(float)

            df = pd.DataFrame({"close": s})

        elif isinstance(df, pd.DataFrame):

            if "close" not in df.columns:

                df = df.rename(columns={df.columns[0]: "close"})

            df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)

        else:

            df = pd.DataFrame(
                {"close": pd.to_numeric(pd.Series(df), errors="coerce").astype(float)}
            )

        s = df["close"]

        # Rolling means

        fast = s.rolling(self.fast, min_periods=self.fast).mean()

        slow = s.rolling(self.slow, min_periods=self.slow).mean()

        # Initialize zeros; only compute where both windows are valid

        sig = pd.Series(0.0, index=s.index, name=f"sma_cross_{self.fast}_{self.slow}")

        m = fast.notna() & slow.notna()

        sig.loc[m] = (fast.loc[m] > slow.loc[m]).astype(float) - (
            fast.loc[m] < slow.loc[m]
        ).astype(float)

        return sig


# --- Register common SMACross specs with the global registry ---
try:
    _registered_sma_cross  # type: ignore[name-defined]
except NameError:
    from ..base import FactorSpec, registry as AlphaRegistry

    # Default example registration
    AlphaRegistry.register(
        FactorSpec(
            name="sma_cross_10_30",
            factory=lambda: SmaCross(fast=10, slow=30),
        )
    )
    _registered_sma_cross = True
