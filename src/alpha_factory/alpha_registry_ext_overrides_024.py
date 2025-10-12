# === v0.2.4 overrides — DuckDB JSON-safe + no self.con + auto 'runs' view ===
from __future__ import annotations
from alpha_factory.alpha_registry import AlphaRegistry


def _ext_get_con(self):
    import duckdb

    con = getattr(self, "_ext_con", None)
    if con is not None:
        return con
    if hasattr(self, "con") and getattr(self, "con") is not None:
        self._ext_con = self.con
        return self._ext_con
    for attr in ("path", "db_path", "database"):
        p = getattr(self, attr, None)
        if isinstance(p, str) and p:
            try:
                self._ext_con = duckdb.connect(p)
                return self._ext_con
            except Exception:
                pass
    self._ext_con = duckdb.connect(":memory:")
    return self._ext_con


def _table_exists(con, name: str) -> bool:
    q = "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_name = ?"
    return con.execute(q, [name]).fetchone()[0] > 0


def _list_tables(con):
    return [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type IN ('BASE TABLE','VIEW')"
        ).fetchall()
    ]


def _cols_for(con, tbl: str) -> dict[str, bool]:
    try:
        info = con.execute(f"PRAGMA table_info({tbl})").fetchall()
    except Exception:
        return {}
    names = {str(r[1]).lower(): True for r in info}
    return names


def _ensure_runs_view(self):
    """
    Ensure a view named 'runs' exists, compatible with analytics:
      required: metrics
      alpha_id is mapped from: alpha_id -> config_hash -> id::TEXT
      optional: run_id, timestamp, tags, config_hash
    """
    con = _ext_get_con(self)
    if _table_exists(con, "runs"):
        return

    candidates = _list_tables(con)
    preferred = [
        "registry_runs",
        "alpha_runs",
        "runs_log",
        "alphas",
        "registry",
        "results",
    ]
    order = preferred + [t for t in candidates if t not in preferred]

    for tbl in order:
        cols = _cols_for(con, tbl)
        if not cols:
            continue
        if ("metrics" in cols) and (
            "alpha_id" in cols or "config_hash" in cols or "id" in cols
        ):
            # alpha_id fallback
            if "alpha_id" in cols:
                alpha_expr = "alpha_id AS alpha_id"
            elif "config_hash" in cols:
                alpha_expr = "config_hash AS alpha_id"
            else:
                alpha_expr = "CAST(id AS VARCHAR) AS alpha_id"

            runid_col = (
                "run_id" if "run_id" in cols else ("id" if "id" in cols else None)
            )
            ts_col = (
                "timestamp"
                if "timestamp" in cols
                else (
                    "ts"
                    if "ts" in cols
                    else (
                        "created_at"
                        if "created_at" in cols
                        else ("time" if "time" in cols else None)
                    )
                )
            )
            tags_col = (
                "tags"
                if "tags" in cols
                else (
                    "labels"
                    if "labels" in cols
                    else ("label" if "label" in cols else None)
                )
            )
            cfg_col = (
                "config_hash"
                if "config_hash" in cols
                else (
                    "cfg_hash"
                    if "cfg_hash" in cols
                    else ("config" if "config" in cols else None)
                )
            )

            select_parts = [alpha_expr, "metrics"]
            select_parts.append(
                f"{runid_col} AS run_id" if runid_col else "uuid() AS run_id"
            )
            select_parts.append(
                f"{ts_col} AS timestamp" if ts_col else "CURRENT_TIMESTAMP AS timestamp"
            )
            select_parts.append(f"{tags_col} AS tags" if tags_col else "NULL AS tags")
            select_parts.append(
                f"{cfg_col} AS config_hash" if cfg_col else "NULL AS config_hash"
            )
            select_sql = ", ".join(select_parts)
            con.execute(f"CREATE VIEW runs AS SELECT {select_sql} FROM {tbl}")
            return

    # Fallback: empty compatible view
    con.execute(
        """
      CREATE VIEW runs AS
      SELECT CAST(NULL AS VARCHAR) AS alpha_id,
             CAST(NULL AS VARCHAR) AS run_id,
             CAST(NULL AS TIMESTAMP) AS timestamp,
             CAST(NULL AS VARCHAR) AS tags,
             CAST(NULL AS JSON) AS metrics,
             CAST(NULL AS VARCHAR) AS config_hash
      WHERE 1=0
    """
    )


def _json_metric_expr(metric: str) -> str:
    # JSON-only extractor (older DuckDB friendly): CAST the JSON to DOUBLE.
    # Produces: TRY_CAST(json_extract(metrics, '$.sharpe') AS DOUBLE)
    return "TRY_CAST(json_extract(metrics, '$.' || '{m}') AS DOUBLE)".format(m=metric)


def _ovr_get_summary(self, metric: str, filters: dict | None = None):
    con = _ext_get_con(self)
    _ensure_runs_view(self)
    val = _json_metric_expr(metric)
    where, params = ["value IS NOT NULL"], []
    if filters:
        if filters.get("alpha_id"):
            where.append("alpha_id = ?")
            params.append(filters["alpha_id"])
        if filters.get("tag"):
            where.append("contains(tags, ?)")
            params.append(filters["tag"])
        if filters.get("since"):
            where.append("timestamp >= TIMESTAMP ?")
            params.append(filters["since"])
        if filters.get("until"):
            where.append("timestamp < TIMESTAMP ?")
            params.append(filters["until"])
        if filters.get("config_hash"):
            where.append("config_hash = ?")
            params.append(filters["config_hash"])
        if filters.get("where_sql"):
            where.append(filters["where_sql"])
    q = f"""
    WITH base AS (
      SELECT alpha_id, run_id, timestamp, tags, {val} AS value, config_hash
      FROM runs
    )
    SELECT alpha_id,
           COUNT(*) AS n,
           AVG(value) AS mean,
           STDDEV_SAMP(value) AS std,
           MIN(value) AS min,
           quantile(value, 0.25) AS q25,
           MEDIAN(value) AS median,
           quantile(value, 0.75) AS q75,
           MAX(value) AS max
    FROM base
    WHERE {' AND '.join(where)}
    GROUP BY alpha_id
    """
    return con.execute(q, params).df()


def _ovr_compare(
    self,
    alpha_ids: list[str],
    metric: str,
    *,
    since: str | None = None,
    until: str | None = None,
):
    import pandas as pd

    if not alpha_ids:
        return pd.DataFrame()
    con = _ext_get_con(self)
    _ensure_runs_view(self)
    val = _json_metric_expr(metric)
    ids = ",".join([f"'{x}'" for x in alpha_ids])
    where, params = [f"alpha_id IN ({ids})", "val IS NOT NULL"], []
    if since:
        where.append("timestamp >= TIMESTAMP ?")
        params.append(since)
    if until:
        where.append("timestamp < TIMESTAMP ?")
        params.append(until)
    q = f"""
    WITH base AS (
      SELECT alpha_id, run_id, timestamp, {val} AS val
      FROM runs
    ),
    flt AS (
      SELECT * FROM base WHERE {' AND '.join(where)}
    ),
    ranked AS (
      SELECT alpha_id, run_id, timestamp, val,
             ROW_NUMBER() OVER (PARTITION BY alpha_id ORDER BY val DESC) AS rn
      FROM flt
    )
    SELECT alpha_id, val FROM ranked WHERE rn=1
    """
    df = con.execute(q, params).df()
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index=None, columns="alpha_id", values="val", aggfunc="first")


def _ovr_rank(
    self,
    metric: str,
    filters: dict | None = None,
    top_n: int = 20,
    ascending: bool | None = None,
):
    con = _ext_get_con(self)
    _ensure_runs_view(self)
    val = _json_metric_expr(metric)
    where, params = ["value IS NOT NULL"], []
    if filters:
        if filters.get("alpha_id"):
            where.append("alpha_id = ?")
            params.append(filters["alpha_id"])
        if filters.get("tag"):
            where.append("contains(tags, ?)")
            params.append(filters["tag"])
        if filters.get("since"):
            where.append("timestamp >= TIMESTAMP ?")
            params.append(filters["since"])
        if filters.get("until"):
            where.append("timestamp < TIMESTAMP ?")
            params.append(filters["until"])
        if filters.get("config_hash"):
            where.append("config_hash = ?")
            params.append(filters["config_hash"])
        if filters.get("where_sql"):
            where.append(filters["where_sql"])
    op = "ASC" if (ascending is True) else "DESC"
    q = f"""
    WITH base AS (
      SELECT alpha_id, run_id, timestamp, tags, {val} AS value, config_hash
      FROM runs
    )
    SELECT alpha_id, run_id, timestamp, tags, value
    FROM base
    WHERE {' AND '.join(where)}
    ORDER BY value {op}
    LIMIT {int(top_n)}
    """
    return con.execute(q, params).df()


def _ensure_runs_meta(con):
    con.execute(
        """
    CREATE TABLE IF NOT EXISTS runs_metadata (
      run_id TEXT PRIMARY KEY,
      alpha_id TEXT NOT NULL,
      run_hash TEXT,
      timestamp TIMESTAMP,
      source_version TEXT,
      config_hash TEXT,
      config_diff TEXT,
      tags TEXT,
      notes TEXT
    );
    """
    )


def _ovr_register_run(self, run_info: dict) -> str:
    import uuid
    import json

    con = _ext_get_con(self)
    _ensure_runs_meta(con)
    run_id = run_info.get("run_id") or str(uuid.uuid4())
    d = {
        "run_id": run_id,
        "alpha_id": run_info["alpha_id"],
        "run_hash": run_info.get("run_hash"),
        "timestamp": run_info.get("timestamp"),
        "source_version": run_info.get("source_version"),
        "config_hash": run_info.get("config_hash"),
        "config_diff": (
            json.dumps(run_info.get("config_diff"))
            if isinstance(run_info.get("config_diff"), dict)
            else run_info.get("config_diff")
        ),
        "tags": run_info.get("tags"),
        "notes": run_info.get("notes"),
    }
    con.execute(
        """
      INSERT OR REPLACE INTO runs_metadata
      (run_id, alpha_id, run_hash, timestamp, source_version, config_hash, config_diff, tags, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        list(d.values()),
    )
    return run_id


def _ovr_get_lineage(self, alpha_id: str):
    con = _ext_get_con(self)
    _ensure_runs_meta(con)
    return con.execute(
        "SELECT * FROM runs_metadata WHERE alpha_id = ? ORDER BY timestamp DESC",
        [alpha_id],
    ).df()


AlphaRegistry.get_summary = _ovr_get_summary
AlphaRegistry.compare = _ovr_compare
AlphaRegistry.rank = _ovr_rank
AlphaRegistry.register_run = _ovr_register_run
AlphaRegistry.get_lineage = _ovr_get_lineage
# === end overrides ===
