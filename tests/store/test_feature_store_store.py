import datetime as dt

from src.store.feature_store import FeatureStore

import pandas as pd
import pytest

try:
    import duckdb  # noqa

    DUCK = True
except Exception:
    DUCK = False

pytestmark = pytest.mark.skipif(not DUCK, reason="duckdb not installed")


def test_upsert_and_query_roundtrip(tmp_path):
    db = tmp_path / "fs.duckdb"
    fs = FeatureStore(str(db))

    rows = [
        {
            "symbol": "EURUSD",
            "ts": dt.datetime(2024, 1, 1, 0, tzinfo=dt.timezone.utc),
            "name": "bb_width",
            "value": 0.1,
        },
        {
            "symbol": "EURUSD",
            "ts": dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc),
            "name": "bb_width",
            "value": 0.2,
        },
        {
            "symbol": "EURUSD",
            "ts": dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc),
            "name": "ma_slope",
            "value": -0.5,
        },
    ]
    n = fs.upsert(rows)
    assert n == 3

    df = fs.query("EURUSD")
    assert len(df) == 3
    assert set(df["name"]) == {"bb_width", "ma_slope"}

    wide = fs.pivot_wide("EURUSD")
    assert list(wide.columns) == ["ts", "bb_width", "ma_slope"]
    assert pd.notna(
        wide.loc[
            wide["ts"] == pd.Timestamp("2024-01-01 01:00:00+0000", tz="UTC"), "ma_slope"
        ]
    ).any()
