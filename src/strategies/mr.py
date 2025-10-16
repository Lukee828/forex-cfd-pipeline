from __future__ import annotations
import pandas as pd
from dataclasses import dataclass
from .base import Strategy, StrategyResult

@dataclass
class MeanReversion(Strategy):
    lookback: int = 20
    z: float = 1.0
    def fit(self, df: pd.DataFrame) -> None:
        pass
    def signals(self, df: pd.DataFrame) -> StrategyResult:
        c = df["close"].astype(float)
        ma = c.rolling(self.lookback).mean()
        sd = c.rolling(self.lookback).std().replace(0, pd.NA).bfill().ffill()
        z = (c - ma) / sd
        sig = (z * -1.0).clip(-3,3)
        out = sig.where(sig.abs() >= self.z, 0.0).apply(lambda x: 1.0 if x>0 else (-1.0 if x<0 else 0.0))
        return StrategyResult(out.fillna(0.0), {"ma": ma})

