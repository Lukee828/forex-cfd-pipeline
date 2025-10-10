import pandas as pd
from structure.overbalance import overbalance


def test_overbalance_shape():
    pivots = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
            "close": [1, 2, 3, 2, 4],
            "pivot": [False, True, False, True, False],
        }
    )
    ob = overbalance(pivots)
    assert len(ob) == len(pivots)
