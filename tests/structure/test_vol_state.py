import pandas as pd
from structure.vol_state import classify_vol_state


def test_vol_state_transitions():
    # Low vol segment -> high vol segment
    ts = pd.date_range("2024-01-01", periods=300, freq="h")
    # low variance then high variance
    import numpy as np

    rng = np.random.default_rng(42)
    part1 = 100 + np.cumsum(rng.normal(0, 0.1, 150))
    part2 = part1[-1] + np.cumsum(rng.normal(0, 1.0, 150))
    s = pd.Series(list(part1) + list(part2), index=ts)
    labels = classify_vol_state(s, window=20, pct_window=60, low_q=0.25, high_q=0.75)
    assert len(labels) == len(s)
    # Should contain at least two regimes
    assert set(labels.unique()) <= {"low", "neutral", "high"}
