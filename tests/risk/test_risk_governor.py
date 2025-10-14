import numpy as np
import pandas as pd
from zigzagob.alpha_factory.risk_governor import RiskGovernor, GovernorConfig


def _equity_series(n=300, seed=7):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0003, 0.01, n)
    eq = (1 + pd.Series(rets)).cumprod()
    eq.index = pd.RangeIndex(n)
    return eq


def test_dd_throttle_reacts_to_drawdown():
    eq = _equity_series(400)
    # inject controlled drawdown
    eq.iloc[200:220] *= 0.90  # ~10% drop segment
    gov = RiskGovernor(GovernorConfig(dd_limit=0.05, dd_window=100, vol_target=None))
    df = gov.compute(eq)
    # throttle should drop below 1 near the drawdown trough
    assert df["throttle"].iloc[215] < 1.0
    # and recover later
    assert df["throttle"].iloc[-1] > df["throttle"].iloc[215]


def test_vol_throttle_scales_when_over_target():
    eq = _equity_series(300, seed=9)
    # amplify volatility on a window
    eq.iloc[100:150] = eq.iloc[100] * (1 + (eq.iloc[100:150] / eq.iloc[100] - 1) * 3)
    gov = RiskGovernor(GovernorConfig(dd_limit=0.2, dd_window=60, vol_target=0.10, vol_window=30))
    df = gov.compute(eq)
    # somewhere in the high-vol window, vol throttle should be < 1
    assert (df["vol_thr"].iloc[110:140] < 1.0).any()
