from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Iterable, Iterator, List
import numpy as np

from src.risk.risk_governor import RiskGovernor, RiskGovernorConfig

@dataclass
class GovernorParams:
    enabled: bool = True
    # drawdown
    dd_window: int = 100
    max_drawdown: float = 0.20
    dd_floor_scale: float = 0.25
    # vol (aliases match your test config style)
    vol_target_annual: float = 0.15
    vol_min_scale: float = 0.25
    vol_max_scale: float = 2.00
    vol_window: int = 30
    trading_days: int = 252

    def to_cfg(self) -> RiskGovernorConfig:
        return RiskGovernorConfig(
            dd_window=self.dd_window,
            max_drawdown=self.max_drawdown,
            dd_floor_scale=self.dd_floor_scale,
            vol_target_annual=self.vol_target_annual,
            vol_min_scale=self.vol_min_scale,
            vol_max_scale=self.vol_max_scale,
            vol_window=self.vol_window,
            trading_days=self.trading_days,
        )

class RiskGovernedSizer:
    """Wrap sizing with RiskGovernor. Call step(price, equity) -> (scale, info)."""
    def __init__(self, params: GovernorParams):
        self.params = params
        self._rg = RiskGovernor(params.to_cfg()) if params.enabled else None
        self._last_price: Optional[float] = None

    def step(self, price: float, equity: float) -> Tuple[float, Dict]:
        if not self.params.enabled:
            return 1.0, {"mode": "off"}

        if self._last_price is None:
            r = 0.0
        else:
            r = (price - self._last_price) / self._last_price if self._last_price else 0.0
        self._last_price = float(price)

        scale, info = self._rg.update(equity_value=float(equity), ret=float(r))
        return float(scale), info