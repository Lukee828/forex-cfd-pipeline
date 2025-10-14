from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import pathlib
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pandas as pd

try:
    import duckdb  # type: ignore

    _HAS_DUCKDB = True
except Exception:  # pragma: no cover
    duckdb = None  # type: ignore
    _HAS_DUCKDB = False

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    name: str
    config_hash: str
    created_at: str
    metrics_json: str
    notes: str


class AlphaRegistry:
    """
    Minimal, production-lean registry for alpha runs with links to FeatureStore features.

    Tables:
      - runs(run_id PK/unique, name, config_hash, created_at, metrics_json, notes)
      - run_features(run_id, feature_id) unique (run_id, feature_id)
    """

    def __init__(self, path: str | os.PathLike = "registry.duckdb") -> None:
        self.path = str(path)
        self.backend = self._select_backend(self.path)
        self._conn = self._connect()
        self._init_schema()

    # ------------------------------ backend ------------------------------
    def _select_backend(self, path: str) -> str:
        p = str(path).lower()
        if p.endswith(".duckdb") and _HAS_DUCKDB:
            return "duckdb"
        if p.endswith(".sqlite") or p.endswith(".db"):
            return "sqlite"
        return "duckdb" if _HAS_DUCKDB else "sqlite"

    def _connect(self):
        pathlib.Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        if self.backend == "duckdb":
            if not _HAS_DUCKDB:
                raise RuntimeError("DuckDB not installed; use .sqlite/.db or install duckdb.")
            return duckdb.connect(self.path)  # type: ignore
        return sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)

    # ------------------------------ schema ------------------------------
    def _init_schema(self) -> None:
        if self.backend == "duckdb":
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT,
                    name TEXT,
                    config_hash TEXT,
                    created_at TIMESTAMP,
                    metrics_json TEXT,
                    notes TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_features (
                    run_id TEXT,
                    feature_id TEXT
                )
                """
            )
            self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_pk ON runs(run_id)")
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_run_features_uniq ON run_features(run_id, feature_id)"
            )
        else:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT,
                    config_hash TEXT,
                    created_at TEXT,
                    metrics_json TEXT,
                    notes TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS run_features (
                    run_id TEXT,
                    feature_id TEXT,
                    PRIMARY KEY (run_id, feature_id)
                )
                """
            )
            self._conn.commit()

    # ------------------------------ utils ------------------------------
    @staticmethod
    def _now_z() -> str:
        return dt.datetime.utcnow().strftime(ISO_FMT)

    @staticmethod
    def _mkid() -> str:
        return uuid.uuid4().hex

    # ------------------------------ api ------------------------------
    def register_run(
        self,
        name: str,
        config_hash: str,
        metrics: Dict[str, Any],
        feature_ids: Optional[Iterable[str]] = None,
        notes: str = "",
    ) -> RunMeta:
        """Register one alpha run (with optional links to FeatureStore feature_ids)."""
        rid = self._mkid()
        created_at = self._now_z()
        metrics_json = json.dumps(metrics, sort_keys=True)

        if self.backend == "duckdb":
            self._conn.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                [rid, name, config_hash, created_at, metrics_json, notes],
            )
            if feature_ids:
                self._conn.register("_fid", pd.DataFrame({"feature_id": list(feature_ids)}))
                try:
                    # CROSS JOIN with constant run_id
                    self._conn.execute(
                        "INSERT INTO run_features SELECT ?, feature_id FROM _fid",
                        [rid],
                    )
                finally:
                    with contextlib.suppress(Exception):
                        self._conn.unregister("_fid")
        else:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (rid, name, config_hash, created_at, metrics_json, notes),
            )
            if feature_ids:
                rows = [(rid, fid) for fid in feature_ids]
                cur.executemany(
                    "INSERT OR REPLACE INTO run_features (run_id, feature_id) VALUES (?, ?)",
                    rows,
                )
            self._conn.commit()

        return RunMeta(
            run_id=rid,
            name=name,
            config_hash=config_hash,
            created_at=created_at,
            metrics_json=metrics_json,
            notes=notes,
        )

    def get_latest(self, name: str) -> Dict[str, Any]:
        """Return the most recent run for a given name."""
        if self.backend == "duckdb":
            row = self._conn.execute(
                "SELECT * FROM runs WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                [name],
            ).fetchone()
            cols = [d[0] for d in self._conn.description]
            return dict(zip(cols, row)) if row else {}
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT * FROM runs WHERE name = ? ORDER BY created_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        if not row:
            return {}
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def get_best(self, name: str, by_metric: str, higher_is_better: bool = True) -> Dict[str, Any]:
        """Return the best run by a numeric metric stored in metrics_json."""
        order = "DESC" if higher_is_better else "ASC"
        if self.backend == "duckdb":
            # DuckDB JSON: use ->> to extract text, cast to DOUBLE
            q = f"""
            SELECT *, CAST(json_extract_string(metrics_json, '$.{by_metric}') AS DOUBLE) AS metric
            FROM runs
            WHERE name = ?
            ORDER BY metric {order}
            LIMIT 1
            """
            row = self._conn.execute(q, [name]).fetchone()
            cols = [d[0] for d in self._conn.description]
            return dict(zip(cols, row)) if row else {}
        else:
            cur = self._conn.cursor()
            rows = cur.execute(
                "SELECT * FROM runs WHERE name = ?",
                (name,),
            ).fetchall()
            if not rows:
                return {}
            cols = [d[0] for d in cur.description]
            best = None
            best_val = None
            for r in rows:
                rec = dict(zip(cols, r))
                try:
                    m = json.loads(rec["metrics_json"]).get(by_metric, None)
                    v = float(m) if m is not None else None
                except Exception:
                    v = None
                if v is None:
                    continue
                if best is None:
                    best, best_val = rec, v
                else:
                    if higher_is_better and v > best_val:
                        best, best_val = rec, v
                    if not higher_is_better and v < best_val:
                        best, best_val = rec, v
            return best or {}

    def search(
        self,
        name: Optional[str] = None,
        config_hash: Optional[str] = None,
        since: Optional[pd.Timestamp] = None,
        until: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """Return a DataFrame of runs matching filters."""
        clauses, params = [], []
        if name is not None:
            clauses.append("name = ?")
            params.append(name)
        if config_hash is not None:
            clauses.append("config_hash = ?")
            params.append(config_hash)
        if self.backend == "duckdb":
            if since is not None:
                clauses.append("created_at >= ?")
                params.append(pd.to_datetime(since).to_pydatetime())
            if until is not None:
                clauses.append("created_at < ?")
                params.append(pd.to_datetime(until).to_pydatetime())
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            return self._conn.execute(
                f"SELECT * FROM runs{where} ORDER BY created_at DESC",
                params,
            ).fetch_df()
        else:
            if since is not None:
                clauses.append("created_at >= ?")
                params.append(pd.to_datetime(since).strftime(ISO_FMT))
            if until is not None:
                clauses.append("created_at < ?")
                params.append(pd.to_datetime(until).strftime(ISO_FMT))
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            cur = self._conn.cursor()
            rows = cur.execute(
                f"SELECT * FROM runs{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(rows, columns=cols)

    def list_links(self, run_id: str) -> pd.DataFrame:
        """Return linked feature_ids for a run."""
        if self.backend == "duckdb":
            return self._conn.execute(
                "SELECT feature_id FROM run_features WHERE run_id = ?",
                [run_id],
            ).fetch_df()
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT feature_id FROM run_features WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)

    # ------------------------------ ctx mgmt ------------------------------
    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._conn.close()

    def __enter__(self) -> "AlphaRegistry":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()
