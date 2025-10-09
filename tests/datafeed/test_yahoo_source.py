import pandas as pd
from datetime import datetime, timezone
from datafeed.yahoo_source import YahooPriceSource


def _stub_downloader_ok(ticker: str) -> pd.DataFrame:
    ts = [datetime(2024, 1, 1, h, tzinfo=timezone.utc) for h in range(3)]
    return pd.DataFrame({"timestamp": ts, "close": [1.0, 1.5, 2.0]})


def _stub_downloader_bad(ticker: str) -> pd.DataFrame:
    return pd.DataFrame({"foo": [1, 2, 3]})


def test_yahoo_stub_fetch_ok():
    src = YahooPriceSource(downloader=_stub_downloader_ok)
    df = src.fetch("EURUSD=X")
    assert list(df.columns) == ["timestamp", "close"]
    assert len(df) == 3
    assert df["close"].iloc[-1] == 2.0
    # strictly increasing timestamps
    assert (df["timestamp"].diff().dropna() > pd.Timedelta(0)).all()


def test_yahoo_stub_fetch_bad_raises():
    src = YahooPriceSource(downloader=_stub_downloader_bad)
    try:
        src.fetch("EURUSD=X")
        assert False, "expected failure"
    except RuntimeError as e:
        assert "timestamp, close" in str(e)
