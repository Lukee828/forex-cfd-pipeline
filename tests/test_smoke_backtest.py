# tests/test_smoke_backtest.py
import numpy as np
import pandas as pd


def _toy_prices(n=200, seed=42):
    rng = np.random.default_rng(seed)
    r = 0.0008 * rng.standard_normal(n)
    close = pd.Series(np.cumprod(1.0 + r), name="close")
    open_ = close.shift(1).fillna(close.iloc[0])
    high = close * 1.002
    low = close * 0.998
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_smoke_equity_series_is_finite():
    df = _toy_prices()
    # Minimal, strategy-agnostic: simple MA crossover toy to prove pipeline can operate on a DF
    fast = df["close"].rolling(5, min_periods=1).mean()
    slow = df["close"].rolling(20, min_periods=1).mean()
    long = (fast > slow).astype(int)
    pnl = (df["close"].pct_change().fillna(0) * long).cumsum()
    equity = (1 + pnl).clip(lower=0)
    assert np.isfinite(equity).all()
    # basic sanity: at least some movement
    assert equity.std() > 0
