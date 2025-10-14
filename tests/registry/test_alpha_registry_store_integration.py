import importlib.util
import json
from pathlib import Path

import pandas as pd

from zigzagob.alpha_factory.feature_store import FeatureStore
from zigzagob.alpha_factory.alpha_registry import AlphaRegistry

HAS_DUCKDB = importlib.util.find_spec("duckdb") is not None


def _feat_df():
    ts = pd.date_range("2024-02-01", periods=3, freq="D")
    return pd.DataFrame(
        {"asof": ts.repeat(2), "symbol": ["EURUSD", "XAUUSD"] * 3, "value": range(6)}
    )


def test_registry_with_sqlite_featurelink(tmp_path: Path):
    # Feature store (sqlite)
    fs = FeatureStore(tmp_path / "fs.sqlite")
    fm = fs.register("sma_10", _feat_df(), notes="seed")
    # Registry (sqlite)
    reg = AlphaRegistry(tmp_path / "reg.sqlite")
    run = reg.register_run(
        name="sma_sweep",
        config_hash="abc123",
        metrics={"sharpe": 1.7, "dd": 0.06},
        feature_ids=[fm.feature_id],
        notes="baseline",
    )
    latest = reg.get_latest("sma_sweep")
    assert latest["run_id"] == run.run_id
    best = reg.get_best("sma_sweep", "sharpe", True)
    assert json.loads(best["metrics_json"])["sharpe"] == 1.7
    links = reg.list_links(run.run_id)
    assert links.iloc[0, 0] == fm.feature_id
    # search window
    df = reg.search(name="sma_sweep")
    assert len(df) >= 1
    fs.close()
    reg.close()


if HAS_DUCKDB:

    def test_registry_with_duckdb_featurelink(tmp_path: Path):
        fs = FeatureStore(tmp_path / "fs.duckdb")
        fm = fs.register("rsi_14", _feat_df(), notes="seed")
        reg = AlphaRegistry(tmp_path / "reg.duckdb")
        _ = reg.register_run(
            name="rsi_sweep",
            config_hash="xyz999",
            metrics={"sharpe": 2.1, "dd": 0.05},
            feature_ids=[fm.feature_id],
            notes="d1",
        )
        latest = reg.get_latest("rsi_sweep")
        assert latest and latest["name"] == "rsi_sweep"
        best = reg.get_best("rsi_sweep", "sharpe", True)
        assert best and best["name"] == "rsi_sweep"
        reg.close()
        fs.close()
