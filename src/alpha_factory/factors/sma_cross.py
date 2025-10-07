from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from ..base import Factor, AlphaRegistry, FactorSpec


@dataclass
class SmaCross(Factor):
    name: str = "sma_cross_10_30"
    requires = ("close",)
    fast: int = 10
    slow: int = 30

    def compute(self, df: pd.DataFrame) -> pd.Series:
        for col in self.requires:
            if col not in df.columns:
                raise KeyError(f"missing required column: {col}")
        c = df["close"]
        fast = c.rolling(self.fast, min_periods=self.fast).mean()
        slow = c.rolling(self.slow, min_periods=self.slow).mean()

        # valid only where both MAs exist
        valid = fast.notna() & slow.notna()
        sig = (fast > slow).astype("int8") - (fast < slow).astype("int8")
        sig = sig.where(valid, np.nan).rename(
            self.name
        )  # propagate NaNs during warm-up
        return sig


# auto-register on import
AlphaRegistry.register(FactorSpec(name=SmaCross.name, factory=lambda: SmaCross()))
