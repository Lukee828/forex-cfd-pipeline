from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FeatureFlags:
    """All OFF by default; turn on explicitly in the runner or config."""

    vol_targeting: bool = False
    cost_windows: bool = False
    spread_guard: bool = False
    dual_tp: bool = False
    time_stop: bool = False
    be_gate_opposite: bool = False


@dataclass
class RiskConfig:
    # All inert by default
    target_annual_vol: float = 0.0
    lookback_bars: int = 50
    min_pos_units: float = 0.0
    max_pos_units: float = 0.0
    tp1_rr: float = 0.0
    runner_trail_rr: float = 0.0
    time_stop_bars: int = 0


@dataclass
class SessionGuards:
    trading_bps: float = 0.0
    max_spread_pts: float = 0.0


@dataclass
class RuntimeState:
    """Optional container the runner can keep; purely additive."""

    flags: FeatureFlags = field(default_factory=FeatureFlags)
    risk: RiskConfig = field(default_factory=RiskConfig)
    guards_by_sym: Dict[str, SessionGuards] = field(default_factory=dict)
