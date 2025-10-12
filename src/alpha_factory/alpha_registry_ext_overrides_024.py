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
    # Create from alphas if present; else empty compatible view
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
    else:
        con.execute(
            """
            CREATE OR REPLACE VIEW runs AS
            SELECT
              CAST(NULL AS VARCHAR) AS alpha_id,
              CAST(NULL AS VARCHAR) AS run_id,
              CAST(NULL AS TIMESTAMP) AS timestamp,
              CAST(NULL AS VARCHAR) AS tags,
              CAST(NULL AS JSON) AS metrics,
              CAST(NULL AS VARCHAR) AS config_hash
            WHERE 1=0
        """
        )


def _json_metric_expr(metric: str) -> str:
    # Literal JSON path + COALESCE handles numeric or quoted forms
    return (
        "COALESCE("
        " TRY_CAST(json_extract(metrics, '$.{m}') AS DOUBLE),"
        " TRY_CAST(CAST(json_extract(metrics, '$.{m}') AS VARCHAR) AS DOUBLE)"
        " )"
    ).format(m=metric)


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
AlphaRegistry.get_summary = (
    _ovr_get_summary  # --- provenance: runs_metadata + helpers ---
)


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
