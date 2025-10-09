from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
import pandas as pd

Downloader = Callable[[str], pd.DataFrame]


@dataclass
class YahooPriceSource:
    symbol_map: Optional[dict[str, str]] = None
    downloader: Optional[Downloader] = None

    def _resolve(self, symbol: str) -> str:
        if self.symbol_map and symbol in self.symbol_map:
            return self.symbol_map[symbol]
        return symbol

    def _default_downloader(self, ticker: str) -> pd.DataFrame:
        try:
            import yfinance as yf  # lazy import
        except Exception as exc:
            raise RuntimeError("yfinance is required for YahooPriceSource") from exc
        df = yf.download(ticker, auto_adjust=False, progress=False)
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise RuntimeError(f"Empty data returned for {ticker}")
        df = df.rename(columns={"Adj Close": "AdjClose"})
        if "Close" not in df.columns:
            # prefer AdjClose if Close missing
            if "AdjClose" in df.columns:
                df["Close"] = df["AdjClose"]
            else:
                raise RuntimeError("No Close column in Yahoo response")
        df = df.reset_index().rename(columns={"Date": "timestamp", "Close": "close"})
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
        return df[["timestamp", "close"]].dropna()

    def fetch(self, symbol: str) -> pd.DataFrame:
        ticker = self._resolve(symbol)
        dl = self.downloader or self._default_downloader
        df = dl(ticker)
        if df.empty or not {"timestamp", "close"}.issubset(df.columns):
            raise RuntimeError("Downloader must return columns: timestamp, close")
        # ensure dtypes
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        out = df.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
        return out.reset_index(drop=True)
