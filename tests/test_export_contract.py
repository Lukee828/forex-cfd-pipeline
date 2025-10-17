# tests/test_export_contract.py
import pandas as pd

def test_schema_and_index_monotonic():
    from src.infra.dukascopy_downloader import _normalize
    idx = pd.date_range("2024-01-01", periods=5, freq="T", tz="UTC")
    df = pd.DataFrame(
        {"Open":[1,1,1,1,1],"High":[2,2,2,2,2],"Low":[0,0,0,0,0],"Close":[1,1,1,1,1],"Volume":[10,10,10,10,10]},
        index=idx,
    )
    df.index.name = "Date"
    out = _normalize(df, "EURUSD")
    assert list(out.columns) == ["Open","High","Low","Close","Volume","symbol"]
    assert isinstance(out.index, pd.DatetimeIndex)
    assert str(out.index.tz) == "UTC"
    assert out.index.is_monotonic_increasing
