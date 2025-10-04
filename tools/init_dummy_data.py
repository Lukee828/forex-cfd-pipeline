"""
Generate dummy OHLCV parquet data for testing strategies.
"""

import pandas as pd
import numpy as np
import os

# Symbols to generate
symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

for sym in symbols:
    # 1000 hourly bars from 2022-01-01
    idx = pd.date_range("2022-01-01", periods=1000, freq="H")

    # Random walk around 1.0
    prices = 1.0 + np.cumsum(np.random.randn(len(idx)) * 0.001)

    df = pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.001,
            "low": prices * 0.999,
            "close": prices,
            "volume": 1000,
        },
        index=idx,
    )

    out_path = f"data/{sym}.parquet"
    df.to_parquet(out_path)
    print(f"Wrote {out_path}")
