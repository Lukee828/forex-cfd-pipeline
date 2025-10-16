from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable, Any, Dict

import duckdb
import pandas as pd


class FeatureStore:
    """
    Tiny feature store backed by DuckDB on disk.

    - Tables are created on first upsert
    - Upserts append (idempotence is up to caller via keys)
    - read_df supports simple WHERE clause string
    """

    def __init__(self, db_path: str | Path = "data/feature_store.duckdb") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Use lazy connections (open/close per op) to avoid file locks on CI/Windows
        self._conn_kwargs: Dict[str, Any] = {}

    def _con(self):
        return duckdb.connect(str(self.db_path), **self._conn_kwargs)

    def list_tables(self) -> list[str]:
        with self._con() as con:
            rows = con.sql("SHOW TABLES").fetchall()
        return [r[0] for r in rows]

    def drop(self, name: str) -> None:
        with self._con() as con:
            con.sql(f'DROP TABLE IF EXISTS "{name}"')

    def upsert_df(self, name: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        with self._con() as con:
            # Create table if not exists via CREATE OR REPLACE AS SELECT on first write
            if name not in self.list_tables():
                con.register("df_src", df)
                con.sql(f'CREATE TABLE "{name}" AS SELECT * FROM df_src')
                con.unregister("df_src")
            else:
                con.register("df_src", df)
                con.sql(f'INSERT INTO "{name}" SELECT * FROM df_src')
                con.unregister("df_src")

    def read_df(self, name: str, where: Optional[str] = None,
                columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
        cols = "*"
        if columns:
            cols = ", ".join([f'"{c}"' for c in columns])
        query = f'SELECT {cols} FROM "{name}"'
        if where:
            query += f" WHERE {where}"
        with self._con() as con:
            return con.sql(query).df()