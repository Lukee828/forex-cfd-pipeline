from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List

import numpy as np


def rolling_drawdown(equity: List[float], window: int) -> Tuple[float, float]:
    """
    Compute current and rolling max drawdown over the last `window` points.

    Returns:
        cur_dd: drawdown of the last point vs the max in-window
        max_dd: maximum drawdown within the window
    """
    if not equity:
        return 0.0, 0.0
    x = np.asarray(equity, dtype=float)
    w = min(window, len(x))
    seg = x[-w:]
    peaks = np.maximum.accumulate(seg)
    dd = (peaks - seg) / np.maximum(peaks, 1e-12)
    cur_dd = float(dd[-1])
    max_dd = float(dd.max() if dd.size else 0.0)
    return cur_dd, max_dd


def ewma_vol(rets: List[float], lam: float) -> float:
    """
    EWMA daily volatility (stdev) of returns.
    """
    if not rets:
        return 0.0
    r = np.asarray(rets, dtype=float)
    lam = float(lam)
    if lam <= 0.0 or lam >= 1.0 or r.size == 0:
        return float(np.std(r, ddof=1) if r.size > 1 else np.std(r))
    w = (1.0 - lam) * np.power(lam, np.arange(r.size - 1, -1, -1, dtype=float))
    w /= w.sum()
    mu = float((w * r).sum())
    var = float((w * (r - mu) ** 2).sum())
    sig = np.sqrt(max(var, 0.0))
    return float(sig)


@dataclass
class RiskGovernorConfig:
    # drawdown guard
    dd_window: int = 100
    max_drawdown: float = 0.20
    dd_floor_scale: float = 0.25
    eps: float = 1e-9

    # volatility throttle
    ewma_lambda: float = 0.94
    trading_days: int = 252
    vol_target: float = 0.15        # annualized target vol
    vol_floor: float = 0.25         # min leverage factor
    vol_ceiling: float = 2.0        # max leverage factor


class RiskGovernor:
    """
    Combines a drawdown gate and an EWMA vol throttle to produce a final risk scale.
    """

    def __init__(self, cfg: Optional[RiskGovernorConfig] = None):
        self.cfg = cfg or RiskGovernorConfig()
        self._equity: List[float] = []
        self._rets: List[float] = []

    def update(self, equity_value: float, ret: Optional[float] = None) -> None:
        """
        Feed latest equity and (optionally) return.
        If return is None and we have a previous equity, compute simple return.
        """
        equity_value = float(equity_value)
        if self._equity and ret is None:
            prev = self._equity[-1]
            if prev != 0.0:
                ret = (equity_value - prev) / prev
            else:
                ret = 0.0
        if ret is not None:
            self._rets.append(float(ret))
        self._equity.append(equity_value)

    # --- internal helpers -------------------------------------------------

    def _dd_gate(self) -> Tuple[float, Dict]:
        cur_dd, max_dd = rolling_drawdown(self._equity, self.cfg.dd_window)
        tripped = max_dd >= (self.cfg.max_drawdown - self.cfg.eps)
        scale = self.cfg.dd_floor_scale if tripped else 1.0
        info = {
            "cur_dd": float(cur_dd),
            "max_dd": float(max_dd),
            "tripped": bool(tripped),
            "dd_scale": float(scale),
        }
        return float(scale), info

    def _vol_scale(self) -> Tuple[float, Dict]:
        sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda)
        sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)
        if sig_ann <= 0:
            return 1.0, {"sig_ann": float(sig_ann), "raw": None, "clamped": 1.0}
        target = self.cfg.vol_target
        floor = self.cfg.vol_floor
        ceil = self.cfg.vol_ceiling
        raw = target / float(sig_ann)
        clamped = float(min(max(raw, floor), ceil))
        return clamped, {"sig_ann": float(sig_ann), "raw": float(raw), "clamped": clamped}

    # --- public API -------------------------------------------------------

    def scale(self) -> Tuple[float, Dict]:
        """
        Final scale and info. If DD gate trips, it dominates; otherwise use vol throttle.
        """
        dd_scale, info_dd = self._dd_gate()
        if dd_scale < 1.0 - self.cfg.eps:
            info = {**info_dd, "final_scale": float(dd_scale), "mode": "dd_floor"}
            return float(dd_scale), info
        vol_scale, info_vol = self._vol_scale()
        scale = float(vol_scale)
        info = {**info_dd, **info_vol, "final_scale": scale, "mode": "vol"}
        return scale, info