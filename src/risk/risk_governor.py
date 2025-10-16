from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List

import numpy as np


def rolling_drawdown(equity: List[float], window: int) -> Tuple[float, float]:
    """Current and rolling max drawdown over the last `window` points."""
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


def ewma_vol(rets: List[float], lam: float = 0.94) -> float:
    """EWMA daily volatility (stdev) of returns; defaults to lam=0.94."""
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

    # canonical fields
    ewma_lambda: Optional[float] = None               # if None, derived from vol_window or default 0.94
    trading_days: int = 252
    vol_target: Optional[float] = None
    vol_floor: Optional[float] = None
    vol_ceiling: Optional[float] = None

    # legacy/alias fields expected by tests
    vol_target_annual: Optional[float] = None
    vol_min_scale: Optional[float] = None
    vol_max_scale: Optional[float] = None
    vol_window: Optional[int] = None                  # convert to lambda by (N-1)/N

    def __post_init__(self) -> None:
        # map aliases → canonical
        if self.vol_target is None:
            self.vol_target = self.vol_target_annual if self.vol_target_annual is not None else 0.15
        if self.vol_floor is None:
            self.vol_floor = self.vol_min_scale if self.vol_min_scale is not None else 0.25
        if self.vol_ceiling is None:
            self.vol_ceiling = self.vol_max_scale if self.vol_max_scale is not None else 2.0
        if self.ewma_lambda is None:
            if self.vol_window and self.vol_window > 1:
                self.ewma_lambda = float((self.vol_window - 1) / self.vol_window)
            else:
                self.ewma_lambda = 0.94


class RiskGovernor:
    """DD gate + EWMA vol throttle → final risk scale."""

    def __init__(self, cfg: Optional[RiskGovernorConfig] = None):
        self.cfg = cfg or RiskGovernorConfig()
        self._equity: List[float] = []
        self._rets: List[float] = []

    def update(self, equity_value: float, ret: Optional[float] = None) -> Tuple[float, Dict]:
        """Feed latest equity/return and return (scale, info)."""
        equity_value = float(equity_value)
        if self._equity and ret is None:
            prev = self._equity[-1]
            ret = (equity_value - prev) / prev if prev != 0.0 else 0.0
        if ret is not None:
            self._rets.append(float(ret))
        self._equity.append(equity_value)
        return self.scale()

    # ---- internals ----

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
        sig_daily = ewma_vol(self._rets, self.cfg.ewma_lambda or 0.94)
        sig_ann = sig_daily * np.sqrt(self.cfg.trading_days)
        if sig_ann <= 0:
            return 1.0, {"sig_ann": float(sig_ann), "raw": None, "clamped": 1.0}
        raw = float(self.cfg.vol_target / sig_ann)
        clamped = float(min(max(raw, float(self.cfg.vol_floor)), float(self.cfg.vol_ceiling)))
        return clamped, {"sig_ann": float(sig_ann), "raw": raw, "clamped": clamped}

    # ---- public ----

    def scale(self) -> Tuple[float, Dict]:
        dd_scale, info_dd = self._dd_gate()
        if dd_scale < 1.0 - self.cfg.eps:
            return dd_scale, {**info_dd, "final_scale": float(dd_scale), "mode": "dd_floor"}
        vol_scale, info_vol = self._vol_scale()
        scale = float(vol_scale)
        return scale, {**info_dd, **info_vol, "final_scale": scale, "mode": "vol"}