from __future__ import annotations
import duckdb
from alpha_factory.alpha_registry import AlphaRegistry


def _ext_get_con(self):
    con = getattr(self, "_ext_con", None)
    if con is not None:
        return con
    if hasattr(self, "con") and getattr(self, "con") is not None:
        self._ext_con = self.con
        return self._ext_con
    for attr in ("db_path", "path", "database"):
        p = getattr(self, attr, None)
        if isinstance(p, str) and p:
            self._ext_con = duckdb.connect(p)
            return self._ext_con
    self._ext_con = duckdb.connect(":memory:")
    return self._ext_con


def _ensure_runs_view(self):
    con = _ext_get_con(self)

    # If a runs view exists but lacks `metrics`, drop it so we can recreate correctly.
    try:
        cols = [str(r[1]).lower() for r in con.execute("PRAGMA table_info(runs)").fetchall()]
        if "metrics" not in cols:
            con.execute("DROP VIEW IF EXISTS runs")
        else:
            return  # already good
    except Exception:
        pass  # no runs view yet

    # If baseline `alphas` exists, build a compatible `runs` view from it.
    has_alphas = False
    try:
        has_alphas = len(con.execute("PRAGMA table_info(alphas)").fetchall()) > 0
    except Exception:
        has_alphas = False

    if has_alphas:
        con.execute(
            """
        CREATE OR REPLACE VIEW runs AS
        SELECT
          CAST(config_hash AS VARCHAR) AS alpha_id,
          CAST(id AS VARCHAR)          AS run_id,
          COALESCE(timestamp, CURRENT_TIMESTAMP) AS timestamp,
          tags,
          CAST(metrics AS JSON)        AS metrics,
          config_hash
        FROM alphas
        """
        )
        return

    # Fallback: empty-compatible view
    con.execute(
        """
    CREATE OR REPLACE VIEW runs AS
    SELECT CAST(NULL AS VARCHAR) AS alpha_id,
           CAST(NULL AS VARCHAR) AS run_id,
           CAST(NULL AS TIMESTAMP) AS timestamp,
           CAST(NULL AS VARCHAR) AS tags,
           CAST(NULL AS JSON) AS metrics,
           CAST(NULL AS VARCHAR) AS config_hash
    WHERE 1=0
    """
    )

    # If a runs view already exists, keep it.
    try:
        con.execute("SELECT 1 FROM runs LIMIT 1")
        return
    except Exception:
        pass

    # Prefer building from an existing baseline table.
    has_alphas = False
    try:
        has_alphas = len(con.execute("PRAGMA table_info(alphas)").fetchall()) > 0
    except Exception:
        has_alphas = False

    if has_alphas:
        # Detect timestamp-like column in alphas
        info = con.execute("PRAGMA table_info(alphas)").fetchall()
        cols = {str(r[1]).lower() for r in info}
        if "timestamp" in cols:
            ts_expr = "timestamp"
        elif "ts" in cols:
            ts_expr = "ts"
        elif "created_at" in cols:
            ts_expr = "created_at"
        elif "time" in cols:
            ts_expr = "time"
        else:
            ts_expr = "NULL"

        con.execute(
            f"""
        CREATE OR REPLACE VIEW runs AS
        SELECT
          CAST(config_hash AS VARCHAR) AS alpha_id,
          CAST(id AS VARCHAR)          AS run_id,
          COALESCE({ts_expr}, CURRENT_TIMESTAMP) AS timestamp,
          tags,
          CAST(metrics AS JSON)        AS metrics,
          config_hash
        FROM alphas
        """
        )
        return

    # Fallback: empty compatible view
    con.execute(
        """
      CREATE OR REPLACE VIEW runs AS
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
    # Used inside CTEs where metrics is selected into scope.
    # Example -> TRY_CAST(json_extract(metrics, '$.sharpe') AS DOUBLE)
    return "TRY_CAST(json_extract(metrics, '$.' || '{m}') AS DOUBLE)".format(m=metric)


def _ovr_rank(
    self,
    metric: str,
    filters: dict | None = None,
    top_n: int = 20,
    ascending: bool | None = None,
):
    con = _ext_get_con(self)
    _ensure_runs_view(self)  # ensure 'runs' exists
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
      SELECT
        r.alpha_id,
        r.run_id,
        r.timestamp,
        r.tags,
        r.config_hash,
        a.metrics AS metrics   -- <-- explicit alias from alphas
      FROM runs r
      LEFT JOIN alphas a
        ON CAST(a.id AS VARCHAR) = r.run_id
    ),
    scored AS (
      SELECT
        alpha_id, run_id, timestamp, tags, config_hash,
        metrics,                       -- <-- carry metrics through
        {val} AS value
      FROM base
    )
    SELECT alpha_id, run_id, timestamp, tags, value
    FROM scored
    WHERE {' AND '.join(where)}
    ORDER BY value {op}
    LIMIT {int(top_n)}
    """
    return con.execute(q, params).df()


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


AlphaRegistry.rank = _ovr_rank
AlphaRegistry.get_summary = _ovr_get_summary  # --- provenance: runs_metadata + helpers ---


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


# attach to class
AlphaRegistry.register_run = _ovr_register_run
AlphaRegistry.get_lineage = _ovr_get_lineage


# --- patch: qualify metrics column to avoid binder ambiguity ---
def _json_metric_expr(metric: str) -> str:
    # Used inside CTEs where `metrics` is selected into scope.
    # Example -> TRY_CAST(json_extract(metrics, '$.sharpe') AS DOUBLE)
    return "TRY_CAST(json_extract(metrics, '$.' || '{m}') AS DOUBLE)".format(
        m=metric
    )  # --- end patch ---


# --- patch: use unqualified metrics now that runs view includes it ---
def _json_metric_expr(metric: str) -> str:
    # Used inside CTEs where `metrics` is selected into scope.
    # Example -> TRY_CAST(json_extract(metrics, '$.sharpe') AS DOUBLE)
    return "TRY_CAST(json_extract(metrics, '$.' || '{m}') AS DOUBLE)".format(
        m=metric
    )  # --- end patch ---


# --- v0.2.7 scoped CTE patch: ensure `metrics` is in-scope before scoring ---


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
      SELECT alpha_id, run_id, timestamp, tags, config_hash, metrics
      FROM runs
    ),
    scored AS (
      SELECT alpha_id, run_id, timestamp, tags, config_hash, {val} AS value
      FROM base
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
    FROM scored
    WHERE {' AND '.join(where)}
    GROUP BY alpha_id
    """
    return con.execute(q, params).df()


def _ovr_rank(
    self,
    metric: str,
    filters: dict | None = None,
    top_n: int = 20,
    ascending: bool | None = None,
):
    con = _ext_get_con(self)
    _ensure_runs_view(self)  # ensure 'runs' exists
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
      SELECT
        r.alpha_id,
        r.run_id,
        r.timestamp,
        r.tags,
        r.config_hash,
        a.metrics AS metrics   -- <-- explicit alias from alphas
      FROM runs r
      LEFT JOIN alphas a
        ON CAST(a.id AS VARCHAR) = r.run_id
    ),
    scored AS (
      SELECT
        alpha_id, run_id, timestamp, tags, config_hash,
        metrics,                       -- <-- carry metrics through
        {val} AS value
      FROM base
    )
    SELECT alpha_id, run_id, timestamp, tags, value
    FROM scored
    WHERE {' AND '.join(where)}
    ORDER BY value {op}
    LIMIT {int(top_n)}
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
      SELECT alpha_id, run_id, timestamp, metrics
      FROM runs
      WHERE alpha_id IN ({ids})
    ),
    scored AS (
      SELECT alpha_id, run_id, timestamp, {val} AS val
      FROM base
    ),
    ranked AS (
      SELECT alpha_id, run_id, timestamp, val,
             ROW_NUMBER() OVER (PARTITION BY alpha_id ORDER BY val DESC) AS rn
      FROM scored
      WHERE {' AND '.join(where)}
    )
    SELECT alpha_id, val FROM ranked WHERE rn=1
    """
    df = con.execute(q, params).df()
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index=None, columns="alpha_id", values="val", aggfunc="first")


AlphaRegistry.get_summary = _ovr_get_summary
AlphaRegistry.rank = _ovr_rank
AlphaRegistry.compare = _ovr_compare
# --- end v0.2.7 patch ---
