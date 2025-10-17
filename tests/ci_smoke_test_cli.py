from pathlib import Path
from src.infra.cli_export import main as cli_main


def test_cli_smoke(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FS_DB", str(tmp_path / "fs.duckdb"))
    monkeypatch.setenv("FS_PARQUET_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("PAIRS", "EURUSD")
    monkeypatch.setenv("SPREAD_BPS", "18.0")
    cli_main()
    assert (tmp_path / "exports").exists()
