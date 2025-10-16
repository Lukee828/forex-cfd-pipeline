import pandas as pd

from alpha_factory.feature_store import FeatureStore


def test_feature_store_smoke(tmp_path):
    db = tmp_path / "fs.duckdb"
    fs = FeatureStore(str(db))

    df = pd.DataFrame(
        {
            "sym": ["EURUSD", "GBPUSD"],
            "val": [1, 2],
        }
    )

    # Replace/create table and then read it back
    fs.write_df("features.prices", df, mode="replace")
    out = fs.read_df("select * from features.prices order by val asc")

    assert len(out) == 2
    assert list(out["sym"]) == ["EURUSD", "GBPUSD"]

    fs.close()
