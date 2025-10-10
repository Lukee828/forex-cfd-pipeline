import pandas as pd
from factors.structure_factors import build_structure_features, StructureConfig


def _toy_prices(n=20, start="2024-01-01"):
    ts = pd.date_range(start, periods=n, freq="h")
    # simple up/down jiggle
    close = [100 + (i % 5) - ((i // 5) % 2) * 2 for i in range(n)]
    return pd.DataFrame({"timestamp": ts, "close": close})


def test_build_structure_features_schema():
    prices = _toy_prices(30)
    out = build_structure_features(prices, StructureConfig(pct=1.0))
    cols = set(out.columns)
    for c in ("timestamp", "close", "pivot", "swing", "vol_state"):
        assert c in cols
    assert len(out) == len(prices)


def test_build_structure_features_has_some_pivots():
    prices = _toy_prices(40)
    out = build_structure_features(prices)
    assert out["pivot"].sum() >= 1


def test_build_structure_features_swing_has_values():
    prices = _toy_prices(40)
    out = build_structure_features(prices)
    # at least one swing should be finite
    assert out["swing"].notna().sum() >= 1
