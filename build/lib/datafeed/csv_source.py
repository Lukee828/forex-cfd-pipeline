from __future__ import annotations
from pathlib import Path
import pandas as pd
from .base import PriceSource


class CsvPriceSource(PriceSource):
    """
    Reads OHLC(V) CSV with either:
      - columns: timestamp,open,high,low,close[,volume]
      - or index-as-datetime + close (others optional)
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(
        self, symbol: str, *, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        df = pd.read_csv(self.path)
        # try to detect timestamp column
        ts_col = next(
            (c for c in df.columns if c.lower() in {"timestamp", "time", "date", "datetime"}),
            None,
        )
        if ts_col:
            df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
            df = df.set_index(ts_col)
        else:
            # assume first column already the index
            if not isinstance(df.index, pd.DatetimeIndex):
                # last resort: parse first column as datetime index
                df.set_index(
                    pd.to_datetime(df.iloc[:, 0], utc=True, errors="coerce"),
                    inplace=True,
                )
                df.drop(columns=df.columns[0], inplace=True)

        need = {"close"}
        missing = need - set(c.lower() for c in df.columns)
        if missing:
            # map common aliases
            aliases = {"adjclose": "close", "price": "close"}
            for c in list(df.columns):
                low = c.lower()
                if low in aliases and aliases[low] not in df.columns:
                    df[aliases[low]] = df[c]
            if "close" not in df.columns:
                raise ValueError("CSV must contain a 'close' (or alias) column")

        if start:
            df = df[df.index >= pd.to_datetime(start, utc=True)]
        if end:
            df = df[df.index <= pd.to_datetime(end, utc=True)]
        return df.sort_index()
