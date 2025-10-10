import pandas as pd
from alpha.momentum import roc
from alpha.labels import fwd_return


def test_roc_basic():
    s = pd.Series([100, 105, 110, 121, 133.1])
    out = roc(s, n=1)
    # first is NaN, others ~ +5%, +4.76.., +10%, +10%
    assert out.isna().iloc[0]
    assert out.round(2).iloc[1] == 5.00
    assert out.round(2).iloc[2] == 4.76
    assert out.round(2).iloc[3] == 10.00
    assert out.round(2).iloc[4] == 10.00


def test_fwd_return_h1():
    s = pd.Series([100, 110, 99])
    f = fwd_return(s, horizon=1)
    # (110/100-1)=0.10, (99/110-1)=-0.10, last is NaN
    assert round(f.iloc[0], 2) == 0.10
    assert round(f.iloc[1], 2) == -0.10
    assert pd.isna(f.iloc[2])
