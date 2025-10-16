from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, Iterable, Tuple, Optional

import numpy as np


def rolling_drawdown(equity: Iterable[float], window: int) -> Tuple[float, float]:
    """
    Returns (current_dd, max_dd) over the last `window` points of an equity curve.
    Drawdown is computed as (peak - value) / peak with peak tracked over the window.
    """
    arr = np.asarray(list(equity), dtype=float)
    if arr.size == 0:
        return (0.0, 0.0)
    if window > arr.size:
        window = arr.size
    # Focus on last `window` points
    tail = arr[-window:]
    peaks = np.maximum.accumulate(tail)
    dd = (peaks - tail) / np.where(peaks == 0.0, 1.0, peaks)
    current_dd = float(dd[-1])
    max_dd = float(dd.max(initial=0.0))
    # Guard for NaNs/Infs
    if not np.isfinite(current_dd):
        current_dd = 0.0
    if not np.isfinite(max_dd):
        max_dd = 0.0
    current_dd = max(0.0, min(1.0, current_dd))
    max_dd = max(0.0, min(1.0, max_dd))
    return current_dd, max_dd


def ewma_vol(returns: Iterable[float], lam: float = 0.94) -> float:
    """
    EWMA volatility (daily). lam in [0,1), higher = longer memory.
    Returns standard deviation of the EWMA process.
    """
    r = np.asarray(list(returns), dtype=float)
    if r.size == 0:
        return 0.0
    # Normalize NaNs
    r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
    w = np.array([lam ** (r.size - 1 - i) for i in range(r.size)], dtype=float)
    w /= w.sum() if w.sum() != 0 else 1.0
    mu = np.sum(w * r)
    var = np.sum(w * (r - mu) ** 2)
    sigma = float(np.sqrt(max(0.0, var)))
    return sigma


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class RiskGovernorConfig:
    pass

    def _vol_scale(self) -> Tuple[float, dict]:
        sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda)
        sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)
        if sig_ann <= 0:
            return 1.0, {"sig_ann": float(sig_ann)}

        target = self.cfg.vol_target
        floor = self.cfg.vol_floor
        ceil = self.cfg.vol_ceiling
        raw = target / sig_ann
        clamped = float(min(max(raw, floor), ceil))
        return clamped, {"sig_ann": float(sig_ann), "raw": float(raw), "clamped": clamped}
class RiskGovernor:
    pass

    def _vol_scale(self) -> Tuple[float, dict]:
        sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda)
        sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)
        if sig_ann <= 0:
            return 1.0, {"sig_ann": float(sig_ann)}

        target = self.cfg.vol_target
        floor = self.cfg.vol_floor
        ceil = self.cfg.vol_ceiling
        raw = target / sig_ann
        clamped = float(min(max(raw, floor), ceil))
        return clamped, {"sig_ann": float(sig_ann), "raw": float(raw), "clamped": clamped}
    pass

    def __init__(self, cfg: Optional[RiskGovernorConfig] = None) -> None:
        self.cfg = cfg or RiskGovernorConfig()
        self._equity: Deque[float] = deque(maxlen=max(self.cfg.dd_window, 1))
        self._rets: Deque[float] = deque(maxlen=max(self.cfg.vol_window, 1))

    def _dd_scale(self) -> Tuple[float, dict]:
        cur_dd, max_dd = rolling_drawdown(self._equity, self.cfg.dd_window)
        tripped = max_dd >= (self.cfg.max_drawdown - self.cfg.eps)
return (
            self.cfg.dd_floor_scale if tripped else 1.0,
            {
                "current_dd": cur_dd,
                "max_dd": max_dd,
                "dd_tripped": tripped,
            },
        )
    def update(self, equity_value: float,
