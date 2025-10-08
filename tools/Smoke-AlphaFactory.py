import numpy as np
import pandas as pd
from src.alpha_factory import AlphaRegistry

np.random.seed(0)
close = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, 120)), name="close")
df = pd.DataFrame({"close": close})

names = AlphaRegistry.names()
assert "sma_cross_10_30" in names, f"registry missing example: {names}"

fac = AlphaRegistry.make("sma_cross_10_30")
sig = fac.compute(df)
assert sig.name == "sma_cross_10_30"
assert (sig.isna().sum() == 0) or (sig.isna().sum() >= fac.slow - 1)
assert set(sig.dropna().unique()).issubset({-1, 0, 1})
print("AlphaFactory smoke OK:", names)
