from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer

def _f(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, default))
    except Exception:
        return default

def _i(env: str, default: int) -> int:
    try:
        return int(float(os.getenv(env, default)))
    except Exception:
        return default

def _b(env: str, default: bool) -> bool:
    v = os.getenv(env)
    if v is None:
        return default
    return v.strip().lower() in {"1","true","yes","on"}

@dataclass
class _GovState:
    sizer: Optional[RiskGovernedSizer] = None

_state = _GovState()

def _build() -> Optional[RiskGovernedSizer]:
    if _b("GOV_OFF", False):
        return None
    p = GovernorParams(
        vol_target_annual=_f("GOV_VOL_TARGET", 0.15),
        vol_window=_i("GOV_VOL_WINDOW", 30),
        vol_min_scale=_f("GOV_VOL_MIN_SCALE", 0.25),
        vol_max_scale=_f("GOV_VOL_MAX_SCALE", 2.0),
        dd_window=_i("GOV_DD_WINDOW", 100),
        max_drawdown=_f("GOV_MAX_DD", 0.20),
        dd_floor_scale=_f("GOV_DD_FLOOR", 0.25),
        trading_days=_i("GOV_TRADING_DAYS", 252),
        enabled=True,
    )
    return RiskGovernedSizer(p)

def governor_scale(price: float, equity: float) -> Tuple[float, Dict]:
    """Return (scale, info). If disabled (GOV_OFF=1), returns (1.0, {"mode":"off"})."""
    try:
        if _state.sizer is None:
            _state.sizer = _build()
        if _state.sizer is None:
            return 1.0, {"mode": "off"}
        s, info = _state.sizer.step(float(price), float(equity))
        if s < 0.0:
            s = 0.0
        if s > 2.0:
            s = 2.0
        if not isinstance(info, dict):
            info = {}
        info.setdefault("mode", info.get("mode", "vol"))
        return float(s), info
    except Exception as e:
        return 1.0, {"mode": "error", "err": str(e)}