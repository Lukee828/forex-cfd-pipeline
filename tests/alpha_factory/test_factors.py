import pandas as pd
from src.alpha_factory import registry


def test_compute_shapes_and_nans():
    s = pd.Series(range(300), dtype=float)
    for name in registry.names():
        sig = registry.make(name).compute(s)
        assert len(sig) == len(s), f"{name}: wrong length"
        assert sig.isna().sum() == 0, f"{name}: contains NaN values"
