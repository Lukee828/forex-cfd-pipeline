from typing import List, Dict, Optional
import pandas as pd


class MACrossStrategy:
    """
    Moving-average cross, safe for fast < slow.
    on_bar(window, i) returns a dict with a generic "signal" AND per-symbol entries.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        fast: int = 10,
        slow: int = 50,
        **kwargs
    ):
        self.symbols = list(symbols) if symbols is not None else []
        self.fast = int(fast)
        self.slow = int(slow)
        if self.fast >= self.slow:
            raise ValueError("fast must be < slow")

    def _to_series(self, prices):
        # Accept Series or DataFrame; normalize to Series (first col if DF).
        if isinstance(prices, pd.DataFrame):
            return prices.iloc[:, 0]
        return prices

    def on_bar(self, prices, i: int) -> Dict[str, int]:
        s = self._to_series(prices)
        if s is None or len(s) < self.slow:
            return {}

        # Robust MA calculation without .rolling(min_periods=slow)
        # Use tail slices to avoid pandas validation issues.
        fma = s.tail(self.fast).mean()
        sma = s.tail(self.slow).mean()

        if pd.isna(fma) or pd.isna(sma):
            return {}

        sign = 1 if fma > sma else -1

        out: Dict[str, int] = {"signal": sign}
        keys = self.symbols if self.symbols else ["BASKET"]
        for k in keys:
            out[k] = sign
        return out
