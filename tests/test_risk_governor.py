from math import isclose

import numpy as np

from src.risk.risk_governor import (
    rolling_drawdown, ewma_vol, RiskGovernor, RiskGovernorConfig
)


def test_rolling_drawdown_simple():
    # Equity ramps to 110, drops to 99 (10% drawdown), then recovers slightly
    eq = [100, 105, 110, 108, 102, 99, 101]
    cur, mx = rolling_drawdown(eq, window=10)
    assert isclose(round(mx, 3), 0.100, rel_tol=1e-6)
    assert cur > 0.0  # still in drawdown at the tail


def test_ewma_vol_zero_safe():
    assert ewma_vol([]) == 0.0
    assert ewma_vol([0, 0, 0]) == 0.0


def test_risk_governor_dd_trips_to_floor():
    cfg = RiskGovernorConfig(dd_window=20, max_drawdown=0.10, dd_floor_scale=0.0)
    rg = RiskGovernor(cfg)

    # Build equity that drops ~11% from 100 to 89
    eq = [100, 101, 102, 103, 104, 103, 100, 95, 92, 89]
    rets = np.diff([*eq[:1], *eq]) / np.array([*eq[:1], *eq])[:-1]

    scale = None
    for e, r in zip(eq, rets):
        scale, info = rg.update(e, r)

    assert info["dd_tripped"] is True
    assert scale == 0.0


def test_risk_governor_vol_throttle():
    cfg = RiskGovernorConfig(
        vol_target_annual=0.20, vol_min_scale=0.0, vol_max_scale=1.0, vol_window=30
    )
    rg = RiskGovernor(cfg)

    # High realized vol => scale below 1.0
    eq = 100.0
    rng = np.random.default_rng(0)
    # ~4% daily vol -> ~63% annual
    rets = rng.normal(0.0, 0.04, size=60)
    scale = None
    for r in rets:
        eq *= (1.0 + r)
        scale, info = rg.update(eq, r)

    assert 0.2 < info["vol_ann"] < 1.0  # sanity
    assert 0.0 <= scale <= 1.0
    assert scale < 1.0