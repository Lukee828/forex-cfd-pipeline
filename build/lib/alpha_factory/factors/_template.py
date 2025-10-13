from dataclasses import dataclass
import numpy as np
import pandas as pd
from ..base import Factor, FactorSpec, registry


@dataclass
class MyFactor(Factor):
    n: int = 20

    @property
    def name(self) -> str:
        return f"myfactor_{self.n}"

    def compute(self, s: pd.Series) -> pd.Series:
        # Example: one-step z-score relative to rolling window
        roll = s.rolling(self.n, min_periods=self.n)
        mean = roll.mean()
        std = roll.std()
        z = (s - mean) / std.replace(0, np.nan)
        return z.fillna(0.0)


# Register one or more ready-made specs (copy/edit as needed)
registry.register(FactorSpec(name="myfactor_20", factory=lambda: MyFactor(n=20)))
