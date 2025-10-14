import importlib.util
import pandas as pd
from pathlib import Path

from zigzagob.alpha_factory.feature_store import FeatureStore

HAS_DUCKDB = importlib.util.find_spec("duckdb") is not None


def _dummy_df(n=5):
    ts = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "asof": ts.repeat(2),
            "symbol": (["EURUSD", "XAUUSD"] * n)[: 2 * n],
            "value": range(2 * n),
        }
    )


def test_sqlite_fallback_register_and_get(tmp_path: Path):
    fs = FeatureStore(tmp_path / "store.sqlite")
    df = _dummy_df(3)
    meta = fs.register("feat_sqlite", df)
    assert meta.version == 1
    got = fs.get("feat_sqlite")
    assert len(got) == len(df)
    fs.close()


if HAS_DUCKDB:

    def test_duckdb_register_and_get(tmp_path: Path):
        fs = FeatureStore(tmp_path / "store.duckdb")
        df = _dummy_df(3)
        m1 = fs.register("feat_duck", df, notes="v1")
        assert m1.version == 1
        df2 = df.copy()
        df2["value"] = df2["value"] + 100
        m2 = fs.register("feat_duck", df2, notes="v2")
        assert m2.version == 2
        latest = fs.get("feat_duck")
        assert latest["value"].iloc[0] == df2["value"].iloc[0]
        v1 = fs.get("feat_duck", version=1)
        assert v1["value"].iloc[0] == df["value"].iloc[0]
        fs.close()
