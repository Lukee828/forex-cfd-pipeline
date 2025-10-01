from pathlib import Path
from typing import Dict, Iterable, List
import pandas as pd
from .events import MarketEvent


class ParquetDataFeed:
    def __init__(self, folder: str, symbols: List[str]):
        self.folder = Path(folder)
        self.symbols = symbols
        self.frames: Dict[str, pd.DataFrame] = {}
        for s in symbols:
            p = self.folder / f"{s}.parquet"
            df = pd.read_parquet(p)
            if "timestamp" in df.columns:
                df = df.set_index(pd.to_datetime(df["timestamp"], utc=True)).drop(
                    columns=["timestamp"]
                )
            if not df.index.tz:
                df.index = df.index.tz_localize("UTC")
            # keep only required columns
            df = df[["Open", "High", "Low", "Close", "Volume"]].sort_index()
            self.frames[s] = df
        # align by outer join of indices
        self.index = sorted(set().union(*[df.index for df in self.frames.values()]))

    def stream(self) -> Iterable[MarketEvent]:
        for ts in self.index:
            ohlcv = {}
            for s, df in self.frames.items():
                if ts in df.index:
                    row = df.loc[ts]
                    ohlcv[s] = dict(
                        Open=float(row["Open"]),
                        High=float(row["High"]),
                        Low=float(row["Low"]),
                        Close=float(row["Close"]),
                        Volume=float(row["Volume"]),
                    )
            if ohlcv:
                yield MarketEvent(ts=ts, ohlcv_by_sym=ohlcv)
