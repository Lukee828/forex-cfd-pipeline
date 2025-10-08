from __future__ import annotations
import sqlite3
from pathlib import Path

import pandas as pd


class FeatureStore:
    """
    Tiny SQLite-backed store for prices & provenance.
    DB schema is created by .init() if not present.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    # ---------- internals ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    # ---------- schema ----------
    def init(self) -> None:
        with self._connect() as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS prices (
                    symbol TEXT NOT NULL,
                    ts     INTEGER NOT NULL,
                    close  REAL,
                    PRIMARY KEY (symbol, ts)
                );
                """
            )
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS provenance (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol    TEXT NOT NULL,
                    kind      TEXT NOT NULL,
                    source    TEXT NOT NULL,
                    version   TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    # ---------- prices ----------
    def upsert_prices(self, symbol: str, df: pd.DataFrame) -> int:
        """
        Insert/replace rows from a DataFrame that has:
          - DatetimeIndex (or anything coercible) -> stored as epoch seconds
          - column 'close'
        Returns number of rows written.
        """
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame({"close": pd.Series(df)})

        if "close" not in df.columns:
            first = df.columns[0]
            df = df.rename(columns={first: "close"})

        # Normalize index to int epoch seconds
        idx = pd.to_datetime(df.index)
        ts = (idx.view("int64") // 10**9).astype("int64")
        closes = pd.to_numeric(df["close"], errors="coerce")

        rows = list(zip([symbol] * len(df), ts.tolist(), closes.tolist()))
        with self._connect() as cx:
            cx.executemany(
                "INSERT OR REPLACE INTO prices(symbol, ts, close) VALUES(?,?,?)",
                rows,
            )
        return len(rows)

    def get_prices(self, symbol: str) -> pd.DataFrame:
        with self._connect() as cx:
            cur = cx.execute(
                "SELECT ts, close FROM prices WHERE symbol=? ORDER BY ts ASC",
                (symbol,),
            )
            recs = cur.fetchall()

        if not recs:
            return pd.DataFrame({"close": []})

        ts, close = zip(*recs)
        idx = pd.to_datetime(pd.Series(ts, dtype="int64") * 10**9)
        df = pd.DataFrame({"close": close}, index=idx)
        return df

    # ---------- provenance ----------
    def record_provenance(
        self, symbol: str, kind: str, source: str, version: str
    ) -> int:
        with self._connect() as cx:
            cur = cx.execute(
                """
                INSERT INTO provenance(symbol, kind, source, version)
                VALUES (?,?,?,?)
                """,
                (symbol, kind, source, version),
            )
            return int(cur.lastrowid)
