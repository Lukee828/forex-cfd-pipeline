import pandas as pd
from src.alpha_factory import registry


def test_no_warmup_nan_for_sma_cross():
    s = pd.Series(range(300), dtype=float)
    sig = registry.make("sma_cross_10_30").compute(s)
    assert sig.isna().sum() == 0


def test_rsi_thresh_has_name_and_no_nan():
    s = pd.Series(range(300), dtype=float)
    sig = registry.make("rsi_thresh_14_30_70").compute(s)
    assert isinstance(sig.name, str) and sig.name
    assert sig.isna().sum() == 0
