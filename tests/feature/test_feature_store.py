import pandas as pd
from pathlib import Path
from feature.feature_store import FeatureStore


def _toy_df(n=10):
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.DataFrame({"close": range(n)}, index=idx)


def test_roundtrip(tmp_path: Path):
    store = FeatureStore(tmp_path / "fs.db")
    store.init()
    df = _toy_df(5)
    n = store.upsert_prices("EURUSD", df)
    assert n >= 5
    out = store.get_prices("EURUSD")
    assert len(out) == 5
    assert out["close"].iloc[-1] == 4


def test_provenance(tmp_path: Path):
    store = FeatureStore(tmp_path / "fs.db")
    store.init()
    df = _toy_df(3)
    store.upsert_prices("XAUUSD", df)
    pid = store.record_provenance("XAUUSD", "prices", "csv:test", "v1")
    assert isinstance(pid, int) and pid > 0
