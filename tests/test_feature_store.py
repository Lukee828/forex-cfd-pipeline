import os
from pathlib import Path
import pandas as pd

from src.infra.feature_store import FeatureStore


def test_roundtrip(tmp_path: Path):
    db = tmp_path / "fs.duckdb"
    fs = FeatureStore(db)

    df = pd.DataFrame(
        {
            "pair": ["EURUSD", "GBPUSD", "EURUSD"],
            "t": [1, 2, 3],
            "feat": [0.1, 0.2, 0.3],
        }
    )

    fs.upsert_df("ticks", df)

    all_rows = fs.read_df("ticks")
    assert len(all_rows) == 3
    assert set(all_rows.columns) >= {"pair", "t", "feat"}

    eur = fs.read_df("ticks", where="pair = 'EURUSD'")
    assert len(eur) == 2

    # selective columns
    one_col = fs.read_df("ticks", columns=["feat"])
    assert list(one_col.columns) == ["feat"]