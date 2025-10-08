import pandas as pd
from pathlib import Path
from datafeed.csv_source import CsvPriceSource


def test_csv_roundtrip(tmp_path: Path):
    csv = tmp_path / "eurusd.csv"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="H", tz="UTC"),
            "close": [1.0, 1.1, 1.2, 1.3, 1.4],
        }
    )
    df.to_csv(csv, index=False)
    src = CsvPriceSource(csv)
    out = src.fetch("EURUSD")
    assert len(out) == 5
    assert abs(out["close"].iloc[-1] - 1.4) < 1e-9
