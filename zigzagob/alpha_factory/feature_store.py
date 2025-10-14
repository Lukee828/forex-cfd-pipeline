from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib

import pandas as pd

try:
    import duckdb  # type: ignore

    _HAS_DUCKDB = True
except Exception:  # pragma: no cover
    duckdb = None  # type: ignore
    _HAS_DUCKDB = False

import sqlite3

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass(frozen=True)
class FeatureMeta:
    feature_id: str
    name: str
    version: int
    created_at: str  # ISO8601 Zulu
    source_hash: str
    schema_json: str
    notes: str


class FeatureStore:
    """
    Lightweight versioned feature store.

    Tables:
      - features_meta(feature_id PK/unique, name, version, created_at, source_hash, schema_json, notes)
      - features_data(feature_id, "asof", symbol, value) unique (feature_id, "asof", symbol)
    """

    def __init__(self, path: str | os.PathLike = "store.duckdb") -> None:
        self.path = str(path)
        self.backend = self._select_backend(self.path)
        self._conn = self._connect()
        self._init_schema()

    # ------------------------------ Backend ------------------------------
    def _select_backend(self, path: str) -> str:
        p = path.lower()
        if p.endswith(".duckdb") and _HAS_DUCKDB:
            return "duckdb"
        if p.endswith(".sqlite") or p.endswith(".db"):
            return "sqlite"
        return "duckdb" if _HAS_DUCKDB else "sqlite"

    def _connect(self):
        pathlib.Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        if self.backend == "duckdb":
            if not _HAS_DUCKDB:
                raise RuntimeError(
                    "DuckDB not installed; choose a .sqlite/.db path or install duckdb."
                )
            return duckdb.connect(self.path)  # type: ignore
        return sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)

    # ------------------------------ Schema ------------------------------
    def _init_schema(self) -> None:
        if self.backend == "duckdb":
            # DuckDB: quote "asof" (reserved word) and use UNIQUE indexes
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS features_meta (
                    feature_id TEXT,
                    name TEXT,
                    version INTEGER,
                    created_at TIMESTAMP,
                    source_hash TEXT,
                    schema_json TEXT,
                    notes TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS features_data (
                    feature_id TEXT,
                    "asof" TIMESTAMP,
                    symbol TEXT,
                    value DOUBLE
                )
                """
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_features_meta_pk ON features_meta(feature_id)"
            )
            self._conn.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS idx_features_data_pk ON features_data(feature_id, "asof", symbol)'
            )
        else:
            # SQLite: keep PRIMARY KEYs
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS features_meta (
                    feature_id TEXT PRIMARY KEY,
                    name TEXT,
                    version INTEGER,
                    created_at TEXT,
                    source_hash TEXT,
                    schema_json TEXT,
                    notes TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS features_data (
                    feature_id TEXT,
                    asof TEXT,
                    symbol TEXT,
                    value REAL,
                    PRIMARY KEY (feature_id, asof, symbol)
                )
                """
            )
            self._conn.commit()

    # ------------------------------ Utilities ------------------------------
    @staticmethod
    def _now_z() -> str:
        return dt.datetime.utcnow().strftime(ISO_FMT)

    @staticmethod
    def _hash_source(obj: str | bytes) -> str:
        if isinstance(obj, str):
            obj = obj.encode("utf-8")
        return hashlib.sha256(obj).hexdigest()

    @staticmethod
    def _schema_from_df(df: pd.DataFrame) -> str:
        schema = {c: str(t) for c, t in df.dtypes.items()}
        return json.dumps(schema, sort_keys=True)

    @staticmethod
    def _make_feature_id(name: str, version: int) -> str:
        base = f"{name}:{version}".encode("utf-8")
        return hashlib.blake2b(base, digest_size=10).hexdigest()

    # ------------------------------ API ------------------------------
    def latest_version(self, name: str) -> Optional[int]:
        if self.backend == "duckdb":
            res = self._conn.execute(
                "SELECT max(version) FROM features_meta WHERE name = ?", [name]
            ).fetchone()
        else:
            cur = self._conn.cursor()
            res = cur.execute(
                "SELECT max(version) FROM features_meta WHERE name = ?", (name,)
            ).fetchone()
        return int(res[0]) if res and res[0] is not None else None

    def list_features(self) -> pd.DataFrame:
        if self.backend == "duckdb":
            return self._conn.execute(
                "SELECT * FROM features_meta ORDER BY created_at DESC"
            ).fetch_df()
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM features_meta ORDER BY created_at DESC").fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)

    def register(
        self,
        name: str,
        df: pd.DataFrame,
        source_hash: Optional[str] = None,
        notes: str = "",
        *,
        asof_col: str = "asof",
        symbol_col: str = "symbol",
        value_col: str = "value",
    ) -> FeatureMeta:
        """Register a new version of a feature. Required columns: asof, symbol, value."""
        required = {asof_col, symbol_col, value_col}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")

        out = df[[asof_col, symbol_col, value_col]].copy()
        out[asof_col] = (
            pd.to_datetime(out[asof_col], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        )
        out[symbol_col] = out[symbol_col].astype(str)
        out[value_col] = pd.to_numeric(out[value_col], errors="coerce")

        version = (self.latest_version(name) or 0) + 1
        feature_id = self._make_feature_id(name, version)
        created_at = self._now_z()
        source_hash = source_hash or self._hash_source(out.to_csv(index=False).encode("utf-8"))
        schema_json = self._schema_from_df(out)

        meta = FeatureMeta(
            feature_id=feature_id,
            name=name,
            version=version,
            created_at=created_at,
            source_hash=source_hash,
            schema_json=schema_json,
            notes=notes,
        )

        if self.backend == "duckdb":
            self._conn.execute(
                "INSERT INTO features_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    meta.feature_id,
                    meta.name,
                    meta.version,
                    meta.created_at,
                    meta.source_hash,
                    meta.schema_json,
                    meta.notes,
                ],
            )
            # Register a pandas DataFrame as a DuckDB view (portable across versions)
            _ren = out.rename(columns={asof_col: "asof", symbol_col: "symbol", value_col: "value"})
            self._conn.register("_incoming", _ren)
            try:
                self._conn.execute(
                    'INSERT INTO features_data SELECT ?, "asof", "symbol", "value" FROM _incoming',
                    [meta.feature_id],
                )
            finally:
                # Clean up the registered view
                try:
                    self._conn.unregister("_incoming")
                except Exception:
                    pass
        else:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO features_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    meta.feature_id,
                    meta.name,
                    meta.version,
                    meta.created_at,
                    meta.source_hash,
                    meta.schema_json,
                    meta.notes,
                ),
            )
            rows = [
                (
                    meta.feature_id,
                    pd.to_datetime(r[asof_col]).strftime(ISO_FMT),
                    str(r[symbol_col]),
                    float(r[value_col]) if pd.notna(r[value_col]) else None,
                )
                for r in out.to_dict("records")
            ]
            cur.executemany(
                "INSERT OR REPLACE INTO features_data (feature_id, asof, symbol, value) VALUES (?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()

        return meta

    def get(
        self,
        name: str,
        version: Optional[int] = None,
        *,
        symbols: Optional[Iterable[str]] = None,
        start: Optional[pd.Timestamp] = None,
        end: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """Retrieve feature data by name/version with optional slicing. Returns [asof, symbol, value]."""
        if version is None:
            version = self.latest_version(name)
            if version is None:
                raise KeyError(f"No feature registered with name '{name}'.")

        if self.backend == "duckdb":
            meta = self._conn.execute(
                "SELECT feature_id FROM features_meta WHERE name = ? AND version = ?",
                [name, version],
            ).fetchone()
            if not meta:
                raise KeyError(f"Feature not found: {name} v{version}")
            fid = meta[0]
            clauses, params = ["feature_id = ?"], [fid]
            if start is not None:
                clauses.append('"asof" >= ?')
                params.append(pd.to_datetime(start).to_pydatetime())
            if end is not None:
                clauses.append('"asof" < ?')
                params.append(pd.to_datetime(end).to_pydatetime())
            if symbols is not None:
                syms = list(symbols)
                placeholders = ",".join(["?"] * len(syms))
                clauses.append(f"symbol IN ({placeholders})")
                params.extend(syms)
            where = " AND ".join(clauses)
            df = self._conn.execute(
                f'SELECT "asof", symbol, value FROM features_data WHERE {where} ORDER BY "asof" ASC, symbol ASC',
                params,
            ).fetch_df()
            df["asof"] = pd.to_datetime(df["asof"], utc=True).dt.tz_localize(None)
            return df
        else:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT feature_id FROM features_meta WHERE name = ? AND version = ?",
                (name, version),
            ).fetchone()
            if not row:
                raise KeyError(f"Feature not found: {name} v{version}")
            fid = row[0]
            clauses, params = ["feature_id = ?"], [fid]
            if start is not None:
                clauses.append("asof >= ?")
                params.append(pd.to_datetime(start).strftime(ISO_FMT))
            if end is not None:
                clauses.append("asof < ?")
                params.append(pd.to_datetime(end).strftime(ISO_FMT))
            if symbols is not None:
                syms = list(symbols)
                placeholders = ",".join(["?"] * len(syms))
                clauses.append(f"symbol IN ({placeholders})")
                params.extend(syms)
            where = " AND ".join(clauses)
            q = f"SELECT asof, symbol, value FROM features_data WHERE {where} ORDER BY asof ASC, symbol ASC"
            rows = cur.execute(q, params).fetchall()
            cols = [d[0] for d in cur.description]
            df = pd.DataFrame(rows, columns=cols)
            if not df.empty:
                df["asof"] = pd.to_datetime(df["asof"], utc=True).dt.tz_localize(None)
            return df

    # ------------------------------ Context mgmt ------------------------------
    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._conn.close()

    def __enter__(self) -> "FeatureStore":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()
