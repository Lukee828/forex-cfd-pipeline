from __future__ import annotations
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer

def test_governor_runtime_sanity():
    g = RiskGovernedSizer(GovernorParams(enabled=True, vol_target_annual=0.2, vol_window=30))
    eq = 100_000.0
    prices = [100, 99, 98, 105, 103, 101]
    seen = []
    for i, p in enumerate(prices):
        if i:
            eq *= 1.0 + (p - prices[i-1]) / prices[i-1]
        s, info = g.step(p, eq)
        assert 0.0 <= s <= 2.0
        seen.append(s)
    assert len(seen) == len(prices)