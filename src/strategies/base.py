from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from typing import Dict, Any

@dataclass
class StrategyResult:
    signals: pd.Series   # -1, 0, +1
    info: Dict[str, Any]

class Strategy:
    def fit(self, df: pd.DataFrame) -> None: ...
    def signals(self, df: pd.DataFrame) -> StrategyResult: ...
