import pandas as pd

from datafeed.yahoo_source import YahooPriceSource


def _stub_multiindex_cols(_ticker: str) -> pd.DataFrame:
    # Simulate yfinance download multiindex columns: ('Close','AAPL')
    idx = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame({("Close", "AAPL"): [1.0, 2.0, 3.0]}, index=idx)
    df = df.reset_index().rename(columns={"index": "Datetime"})
    return df


def _stub_tz_naive_index(_ticker: str) -> pd.DataFrame:
    # Naive datetime index + 'Close' column
    idx = pd.date_range("2024-02-01", periods=3, freq="D")  # tz-naive
    df = pd.DataFrame({"Close": [10.0, 11.0, 12.0]}, index=idx)
    df = df.reset_index().rename(columns={"index": "Datetime"})
    return df


def test_yahoo_multiindex_columns_are_flattened():
    src = YahooPriceSource(downloader=_stub_multiindex_cols)
    out = src.fetch("AAPL")
    assert list(out.columns) == ["timestamp", "close"]
    assert len(out) == 3
    assert out["close"].iloc[0] == 1.0


def test_yahoo_tz_naive_is_handled():
    src = YahooPriceSource(downloader=_stub_tz_naive_index)
    out = src.fetch("AAPL")
    assert list(out.columns) == ["timestamp", "close"]
    assert out["timestamp"].dtype == "datetime64[ns]"
    assert out["close"].iloc[-1] == 12.0
