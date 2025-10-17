from pathlib import Path
import pytest

try:
    # soft dependency: test will skip if infra pieces missing
    from src.infra.registry import get_store, TABLES
    from src.infra.export_features import export_risk_snapshot, RiskInputs
except Exception as e:  # pragma: no cover
    pytest.skip(f"integration infra not importable: {e}", allow_module_level=True)


def test_export_risk_snapshot_roundtrip(tmp_path: Path):
    db = tmp_path / "fs.duckdb"
    tbl = export_risk_snapshot(RiskInputs(pair="EURUSD", spread_bps=18.0), db_path=str(db))

    store = get_store(str(db))
    assert tbl in TABLES.values()

    df = store.read_df(tbl)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["pair"] == "EURUSD"
    # columns exist, values may be None if optional modules aren’t present
    assert "sg_spread_bps" in df.columns
    assert "vol_regime" in df.columns
