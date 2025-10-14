from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GovernorConfig:
    dd_limit: float = 0.07  # max rolling peak-to-trough drawdown (fraction)
    dd_window: int = 252  # bars for rolling peak
    vol_target: Optional[float] = 0.12  # annualized target vol (None to disable)
    vol_window: int = 63  # bars for realized vol lookback
    max_gross_exposure: float = 1.0  # cap on gross exposure (1.0 = 100%)
    min_throttle: float = 0.0  # hard floor on throttle
    max_throttle: float = 1.0  # hard cap on throttle


class RiskGovernor:
    """
    Computes a multiplicative throttle in [min_throttle, max_throttle]
    based on rolling drawdown and realized volatility vs target.
    """

    def __init__(self, cfg: Optional[GovernorConfig] = None, *, bars_per_year: int = 252):
        self.cfg = cfg or GovernorConfig()
        self.bars_per_year = bars_per_year

    # -------- metrics --------
    @staticmethod
    def rolling_drawdown(equity: pd.Series, window: int) -> pd.Series:
        peak = equity.rolling(window=window, min_periods=1).max()
        dd = equity / peak - 1.0
        return dd.fillna(0.0)

    def realized_vol(self, ret: pd.Series, window: int) -> pd.Series:
        # daily stdev * sqrt(annualization)
        vol_d = ret.rolling(window=window, min_periods=max(2, int(window / 4))).std()
        return (vol_d * np.sqrt(self.bars_per_year)).bfill().fillna(0.0)

    # -------- throttles --------
    def dd_throttle(self, equity: pd.Series) -> pd.Series:
        dd = self.rolling_drawdown(equity, self.cfg.dd_window).abs()
        # Linear throttle down once dd exceeds limit: limit -> 1, 2*limit -> 0
        lim = max(self.cfg.dd_limit, 1e-8)
        over = (dd - lim).clip(lower=0.0)
        thr = 1.0 - (over / lim)  # dd==lim => 1; dd==2*lim => 0
        return thr.clip(lower=self.cfg.min_throttle, upper=self.cfg.max_throttle)

    def vol_throttle(self, ret: pd.Series) -> pd.Series:
        if self.cfg.vol_target is None or self.cfg.vol_target <= 0:
            return pd.Series(1.0, index=ret.index)
        rv = self.realized_vol(ret, self.cfg.vol_window)
        # Proportional scaling: target / realized (clipped)
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = self.cfg.vol_target / rv.replace(0, np.nan)
        scale = scale.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        return scale.clip(lower=self.cfg.min_throttle, upper=self.cfg.max_throttle)

    # -------- main API --------
    def compute(
        self,
        equity: pd.Series,
        *,
        gross_exposure_hint: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """Return dataframe with columns: dd_thr, vol_thr, expo_thr, throttle."""
        equity = equity.astype(float)
        ret = equity.pct_change().fillna(0.0)

        dd_thr = self.dd_throttle(equity)
        vol_thr = self.vol_throttle(ret)

        if gross_exposure_hint is not None:
            expo_thr = (self.cfg.max_gross_exposure / gross_exposure_hint.replace(0, np.nan)).clip(
                0, self.cfg.max_throttle
            )
            expo_thr = expo_thr.fillna(1.0)
        else:
            expo_thr = pd.Series(1.0, index=equity.index)

        throttle = (dd_thr * vol_thr * expo_thr).clip(self.cfg.min_throttle, self.cfg.max_throttle)
        return pd.DataFrame(
            {"dd_thr": dd_thr, "vol_thr": vol_thr, "expo_thr": expo_thr, "throttle": throttle}
        )

    def apply_position_size(self, base_size: pd.Series, throttle: pd.Series) -> pd.Series:
        return (base_size.astype(float) * throttle.astype(float)).clip(lower=0.0)
