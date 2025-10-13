from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Iterable, Any

import pandas as pd


def _ensure_series_time(ts_like: Any) -> pd.Series:
    """Return a pandas Series of timestamps from either Series or DatetimeIndex."""
    if isinstance(ts_like, pd.Series):
        return ts_like
    if isinstance(ts_like, pd.DatetimeIndex):
        return pd.Series(ts_like)
    # last resort
    return pd.Series(pd.to_datetime(ts_like, errors="raise"))


def _find_close_column(columns: Iterable[Any]) -> Optional[Any]:
    """
    Given arbitrary columns (strings or tuples/MultiIndex levels),
    return the original column object that represents close price.
    Priority: 'adj close'/'adjclose' > 'close'.
    """
    candidate = None
    for c in columns:
        parts: list[str]
        if isinstance(c, tuple):
            parts = [str(p).strip().lower() for p in c if p is not None and str(p) != ""]
        else:
            parts = [str(c).strip().lower()]

        if "adj close" in parts or "adjclose" in parts:
            return c
        if "close" in parts:
            candidate = c
    return candidate


def _normalize_prices_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a yfinance-like DataFrame to two columns: ['timestamp','close'].
    Handles:
      - DatetimeIndex or a time column (Datetime/Date/date/timestamp/time)
      - tz-aware or tz-naive timestamps (returns tz-naive UTC)
      - plain or MultiIndex/tuple columns; looks for 'Adj Close' or 'Close'
    """
    if df is None or len(df) == 0:
        raise RuntimeError("Empty data frame")

    # Extract time series
    ts = None
    if isinstance(df.index, pd.DatetimeIndex):
        ts = _ensure_series_time(df.index)
    else:
        for cand in ("Datetime", "Date", "date", "timestamp", "time"):
            if cand in df.columns:
                ts = pd.to_datetime(df[cand], errors="coerce")
                break
        if ts is None:
            ts = _ensure_series_time(df.index)

    # TZ handling: Series.dt for Series, Index.tz for DatetimeIndex
    if isinstance(ts, pd.Series):
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    else:
        # shouldn’t happen because _ensure_series_time returns Series,
        # but keep a defensive branch
        if getattr(ts, "tz", None) is not None:
            ts = pd.Series(ts.tz_convert("UTC").tz_localize(None))

    # Find the close column without destroying tuple structure
    close_col = _find_close_column(df.columns)
    if close_col is None:
        raise RuntimeError(
            "Downloader must return columns: timestamp, close (Close/Adj Close required)"
        )

    out = (
        pd.DataFrame(
            {
                "timestamp": ts.values,
                "close": pd.to_numeric(df[close_col], errors="coerce"),
            }
        )
        .dropna(subset=["timestamp", "close"])
        .reset_index(drop=True)
    )

    if out.empty:
        raise RuntimeError("No valid rows after normalization")
    return out


@dataclass
class YahooPriceSource:
    """
    Pull recent prices via yfinance and normalize to ['timestamp','close'].

    Optional `downloader(ticker) -> DataFrame` can be injected for testing.
    """

    downloader: Optional[Callable[[str], pd.DataFrame]] = None

    def __post_init__(self) -> None:
        if self.downloader is None:
            self.downloader = self._default_downloader

    @staticmethod
    def _default_downloader(ticker: str) -> pd.DataFrame:
        try:
            import yfinance as yf  # lazy import
        except Exception as exc:
            raise RuntimeError("yfinance is required for YahooPriceSource") from exc

        # Try history(); fall back to download()
        try:
            df = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=False)
            if df is None or df.empty:
                raise ValueError("empty from history()")
        except Exception:
            df = yf.download(
                tickers=ticker,
                period="1mo",
                interval="1d",
                group_by="column",
                auto_adjust=False,
                progress=False,
            )

        if df is None or df.empty:
            raise RuntimeError(f"Empty data returned for {ticker}")

        # Make the time discoverable to _normalize (use a column)
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()  # adds 'Date' or 'Datetime' depending on source
        return df

    def fetch(self, ticker: str) -> pd.DataFrame:
        df = self.downloader(ticker)
        return _normalize_prices_df(df)
