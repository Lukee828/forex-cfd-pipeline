# src/data/sqlite_store.py
import sqlite3
from pathlib import Path
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv(
  symbol TEXT NOT NULL,
  ts     TEXT NOT NULL,
  open   REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY(symbol, ts)
);
"""


class OHLCVStore:
    def __init__(self, db_path="db/market.sqlite"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cn = sqlite3.connect(self.path)
        self.cn.execute("PRAGMA journal_mode=WAL;")
        self.cn.execute(SCHEMA)

    def upsert_frame(self, symbol: str, df: pd.DataFrame):
        df = df.rename(columns=str.lower).copy()
        df["symbol"] = symbol
        df["ts"] = df.index.astype(str)
        cols = ["symbol", "ts", "open", "high", "low", "close", "volume"]
        df[cols].to_sql("ohlcv", self.cn, if_exists="append", index=False)

    def load(self, symbol: str) -> pd.DataFrame:
        q = "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol=? ORDER BY ts"
        df = pd.read_sql(q, self.cn, params=(symbol,))
        df["ts"] = pd.to_datetime(df["ts"])
        return df.set_index("ts")
