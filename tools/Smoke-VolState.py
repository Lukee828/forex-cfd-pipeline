# tools/Smoke-VolState.py
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from src.risk.vol_state import VolStateMachine, infer_vol_regime

rng = np.random.default_rng(42)

# build a deterministic 300-day series with 3 regimes
n = 300
dates = pd.date_range(
    datetime.now(timezone.utc) - timedelta(days=n - 1), periods=n, freq="D"
)
seg = [100.0]
for i in range(1, 100):
    seg.append(seg[-1] * (1 + 0.001 * rng.standard_normal()))
for i in range(100, 200):
    seg.append(seg[-1] * (1 + 0.005 * rng.standard_normal()))
for i in range(200, 300):
    seg.append(seg[-1] * (1 + 0.020 * rng.standard_normal()))
close = pd.Series(seg, index=dates, name="Close")

vsm = VolStateMachine(window=20).fit(close)
reg = vsm.classify_series(close)

# basic assertions: later segment should have more HIGH than the first one
first_high = (reg.iloc[:100] == "HIGH").sum()
last_high = (reg.iloc[-100:] == "HIGH").sum()

print("first_high:", first_high, "last_high:", last_high)
assert (
    last_high > first_high
), "Expected more HIGH regimes in the high-vol tail segment."

# also ensure we can use the convenience function without error
reg2 = infer_vol_regime(close, window=20)
assert set(reg2.dropna().unique()) <= {"LOW", "MEDIUM", "HIGH"}

print("VOLSTATE_OK")
