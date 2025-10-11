from typing import Any, Iterable, Mapping
import duckdb
import pandas as pd

DDL = """
CREATE TABLE IF NOT EXISTS feature_store (
    symbol TEXT,
    ts TIMESTAMPTZ,
    name TEXT,
    value DOUBLE,
    ver TEXT
  )
"""


class FeatureStore:
    def __init__(self, path: str):

        self.con = duckdb.connect(path)
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_store (
                symbol TEXT,
                ts TIMESTAMPTZ,
                name TEXT,
                value DOUBLE,
                ver TEXT
            )
        """
        )
        self.con.execute(
            "CREATE INDEX IF NOT EXISTS idx_fs_sym_ts ON feature_store(symbol, ts)"
        )
        self.con.execute(
            "CREATE INDEX IF NOT EXISTS idx_fs_sym_name_ts ON feature_store(symbol, name, ts)"
        )

    def upsert(self, rows: Iterable[Mapping[str, Any]]) -> int:
        # rows: {symbol, ts (aware datetime), name, value, [ver]}
        data: list[tuple[str, object, str, float, str]] = []
        for r in rows:
            data.append(
                (
                    str(r["symbol"]),
                    r["ts"],
                    str(r["name"]),
                    float(r["value"]),
                    str(r.get("ver", "v1")),
                )
            )
        if not data:
            return 0
        # Emulate upsert on (symbol, ts, name, ver)
        keys = [(s, t, n, v) for (s, t, n, _, v) in data]
        self.con.executemany(
            "DELETE FROM feature_store WHERE symbol=? AND ts=? AND name=? AND ver=?",
            keys,
        )
        self.con.executemany(
            "INSERT INTO feature_store(symbol, ts, name, value, ver) VALUES (?,?,?,?,?)",
            data,
        )
        return len(data)

    def query(self, symbol: str, names=None, start=None, end=None):
        """
        Return LONG dataframe: columns [symbol, ts, name, value].
        """
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_store (
                symbol TEXT,
                ts TIMESTAMPTZ,
                name TEXT,
                value DOUBLE,
                ver TEXT
            )
        """
        )
        sql = "SELECT symbol, ts, name, value FROM feature_store WHERE symbol = ?"
        params = [symbol]
        if names:
            placeholders = ", ".join(["?"] * len(names))
            sql += f" AND name IN ({placeholders})"
            params.extend(list(names))
        if start is not None:
            sql += " AND ts >= ?"
            params.append(start)
        if end is not None:
            sql += " AND ts <= ?"
            params.append(end)
        sql += " ORDER BY ts"
        df = self.con.execute(sql, params).fetch_df()
        if not df.empty:
            import pandas as pd

            df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df

    def pivot_wide(self, symbol: str, names=None, start=None, end=None):
        """
        Wide pivot: index=ts, columns=name, values=value. Columns deterministic.
        """

        df = self.query(symbol, names=names, start=start, end=end)
        if df.empty:
            return pd.DataFrame(columns=["ts"]).set_index("ts").reset_index()
        wide = (
            df.pivot_table(index="ts", columns="name", values="value", aggfunc="last")
            .sort_index()
            .reset_index()
        )
        cols = ["ts"] + sorted([c for c in wide.columns if c != "ts"])
        return wide[cols]


def pivot_wide(
    self, symbol: str, start: str = None, end: str = None, ver: str | None = None
):
    df = self.query(symbol, start, end, ver)
    if df.empty:
        return df
    out = df.pivot(index="ts", columns="name", values="value").reset_index()
    return out
