import pandas as pd
from structure.zigzag import zigzag, ZigZagParams


def test_zigzag_pct_basic():
    s = pd.Series(
        [1, 1.01, 1.02, 1.00, 0.99, 1.03],
        index=pd.date_range("2024-01-01", periods=6, freq="h"),
    )
    zz = zigzag(s, ZigZagParams(pct=1.0))
    assert {"timestamp", "close", "pivot"} <= set(zz.columns)
    assert zz["pivot"].sum() >= 1
