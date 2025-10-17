from __future__ import annotations
import pandas as pd
from dataclasses import dataclass
from .base import Strategy, StrategyResult

@dataclass
class Breakout(Strategy):
    lookback: int = 50
    def fit(self, df: pd.DataFrame) -> None:
        pass
    def signals(self, df: pd.DataFrame) -> StrategyResult:
        hi = df["high"].rolling(self.lookback).max()
        lo = df["low"].rolling(self.lookback).min()
        c = df["close"]
        sig = (c > hi.shift(1)).astype(float) - (c < lo.shift(1)).astype(float)
        return StrategyResult(sig.fillna(0.0), {"hi": hi, "lo": lo})
