from __future__ import annotations
from typing import Any, Dict

try:
    # Case 1: your engine already exposes BacktestEngine
    from .engine import BacktestEngine as _BacktestEngine  # type: ignore

    class BacktestEngine(_BacktestEngine):
        pass

except Exception:
    try:
        # Case 2: engine exposes a class named Backtest or Runner with .run()
        from .engine import Backtest as _Impl  # type: ignore

        class BacktestEngine:
            def __init__(self, df, signals):
                self._impl = _Impl(df, signals)  # type: ignore
            def run(self) -> Any:
                return self._impl.run()  # type: ignore

    except Exception:
        # Case 3: minimal fallback runner (long-only when signal > 0, short when < 0)
        import pandas as pd
        import numpy as np

        class BacktestEngine:
            def __init__(self, df, signals):
                self.df = df
                self.signals = signals
            def run(self) -> Dict[str, Any]:
                c = self.df["close"].astype(float)
                ret = c.pct_change().fillna(0.0)
                pos = (self.signals > 0).astype(int) - (self.signals < 0).astype(int)
                pnl = (pos.shift(1).fillna(0).astype(float) * ret).cumsum()
                eq = (1.0 + pnl).rename("equity")
                return {"equity": eq, "pnl": pnl}
