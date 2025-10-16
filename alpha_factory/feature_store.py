from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import duckdb
import pandas as pd


@dataclass
class FeatureStore:
    """
    Minimal FeatureStore over DuckDB.
    - Uses a single DuckDB file (or :memory:) per instance.
    - write_df(table, df, mode): replace (=CREATE OR REPLACE TABLE) or append.
    - read_df(sql): returns pandas.DataFrame
    """

    db_path: str = ":memory:"
    _con: Optional[duckdb.DuckDBPyConnection] = None

    def __post_init__(self) -> None:
        self._con = duckdb.connect(self.db_path)

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            self._con = duckdb.connect(self.db_path)
        return self._con

    def write_df(self, table: str, df: pd.DataFrame, mode: str = "append") -> None:
        """
        Write a DataFrame into a DuckDB table.
        mode:
          - "replace": CREATE OR REPLACE TABLE <table> AS SELECT * FROM df
          - "append" : CREATE TABLE IF NOT EXISTS (empty schema), then INSERT
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError("df must be a pandas.DataFrame")

        # Register the DataFrame for SQL
        self.con.register("df", df)
        try:
            if mode == "replace":
                self.con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df")
            elif mode == "append":
                # create empty table if it doesn't exist
                self.con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0")
                self.con.execute(f"INSERT INTO {table} SELECT * FROM df")
            else:
                raise ValueError("mode must be 'replace' or 'append'")
        finally:
            # it's fine to leave the relation registered; but we can clean it explicitly:
            try:
                self.con.unregister("df")
            except Exception:
                pass

    def read_df(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).fetchdf()

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None
