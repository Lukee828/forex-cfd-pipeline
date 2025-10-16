from __future__ import annotations
import os
from src.data.dukascopy import BarSpec, get_bars
from src.strategies.mr import MeanReversion
from src.backtest.engine import run_backtest
def test_backtest_pipeline_smoke():
    os.environ["DUKASCOPY_OFFLINE"]="1"
    df = get_bars(BarSpec("EURUSD","H1","2024-01-01","2024-01-15"))
    sig = MeanReversion().signals(df).signals
    res = run_backtest(df, sig)
    assert "summary" in res and "equity_curve" in res
