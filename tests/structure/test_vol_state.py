import pandas as pd
from structure.vol_state import classify_vol_state


def test_vol_state_labels():
    s = pd.Series(range(10), index=pd.date_range("2024-01-01", periods=10, freq="h"))
    labels = classify_vol_state(s)
    assert len(labels) == len(s)
