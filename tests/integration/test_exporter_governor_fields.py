# tests/integration/test_exporter_governor_fields.py
from pathlib import Path
from src.infra.export_features import RiskInputs, gather_risk_features, export_risk_snapshot

def test_gather_has_governor_fields():
    snap = gather_risk_features(RiskInputs(pair="EURUSD", spread_bps=15.0))
    for k in ("rg_scale", "rg_mode", "rg_dd_tripped", "rg_vol_ann"):
        assert k in snap

def test_export_snapshot_table_name(tmp_path: Path):
    db = tmp_path / "fs.duckdb"
    tbl = export_risk_snapshot(RiskInputs(pair="EURUSD", spread_bps=15.0), db_path=str(db))
    assert isinstance(tbl, str)