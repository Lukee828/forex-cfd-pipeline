from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd

# Ensure overrides are active (rank/get_summary/compare/lineage)
import alpha_factory.alpha_registry_ext_overrides_024  # noqa: F401


def _con_for(reg):
    # same pattern used in overrides
    if getattr(reg, "con", None) is not None:
        return reg.con
    for attr in ("db_path", "path", "database"):
        p = getattr(reg, attr, None)
        if isinstance(p, str) and p:
            return duckdb.connect(p)
    return duckdb.connect(":memory:")


def refresh_runs_view(reg) -> None:
    # Idempotent: create a 'runs' view from whatever table exists (alphas baseline)
    con = _con_for(reg)
    # Prefer existing view from overrides; create a compatible one if missing
    try:
        con.execute("SELECT 1 FROM runs LIMIT 1")
        return
    except Exception:
        pass
    # Fallback view built off 'alphas' if present
    try:
        con.execute("SELECT 1 FROM alphas LIMIT 1")
    except Exception:
        # Empty placeholder view
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
        return

    # Detect a timestamp-like column
    cols = {str(r[1]).lower() for r in con.execute("PRAGMA table_info(alphas)").fetchall()}
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


def alerts(
    reg,
    *,
    metric: str,
    min_value: float,
    tag: str | None = None,
    since: str | None = None,
):
    """
    Return rows (alpha_id, run_id, timestamp, tags, value) where metric >= min_value.

    Compat notes:
    - Prefer reg.rank(...) if available.
    - Otherwise, query the DuckDB file directly and try common table/view names.
    """
    import duckdb
    import pandas as pd

    # If there is a native method, use it.
    if hasattr(reg, "rank"):
        filters = {
            "where_sql": f"TRY_CAST(json_extract(metrics, '$.' || '{metric}') AS DOUBLE) >= {float(min_value)}"
        }
        if tag:
            filters["tag"] = tag
        if since:
            filters["since"] = since
        try:
            return reg.rank(metric=metric, filters=filters, top_n=10_000)
        except Exception:
            # fall through to DuckDB compat
            pass

    # ---- DuckDB compat path ----
    # best-effort: locate file path / connection
    db_path = getattr(reg, "db_path", None) or getattr(reg, "path", None)
    if db_path is None:
        # Some implementations expose a connection; try to extract its database path
        conn = getattr(reg, "conn", None) or getattr(reg, "_conn", None)
        if conn is not None:
            try:
                db_path = conn.database
            except Exception:
                db_path = None

    con = duckdb.connect(db_path) if isinstance(db_path, str) else duckdb.connect()

    # We’ll scan the catalog for a JSON-bearing table/view.
    # Priority: runs_view, runs, alpha_runs, registry, alphas
    candidates = ["runs_view", "runs", "alpha_runs", "registry", "alphas"]

    # helper: does a relation have a 'metrics' column?
    def has_metrics(relname: str) -> bool:
        try:
            cols = con.execute(f"PRAGMA table_info('{relname}')").fetchdf()
            return any(c.lower() == "metrics" for c in map(str, cols["name"]))
        except Exception:
            return False

    # try to ensure runs_view exists if your toolkit has a helper
    try:
        # if you have a refresh function in this module, call it
        refresh_runs_view(reg)  # type: ignore[name-defined]
    except Exception:
        pass

    # build a candidate list that actually exists & has metrics
    existing = []
    try:
        tables = con.execute("SELECT name FROM duckdb_tables()").fetchall()
        names = [t[0] for t in tables]
        views = con.execute("SELECT table_name FROM information_schema.views").fetchall()
        names += [v[0] for v in views]
        names = {n.lower() for n in names}
        for c in candidates:
            if c.lower() in names and has_metrics(c):
                existing.append(c)
    except Exception:
        pass

    rel = existing[0] if existing else None
    if rel is None:
        # Absolute fallback: just return an empty DataFrame with typical columns
        return pd.DataFrame(columns=["alpha_id", "run_id", "timestamp", "tags", metric])

    clauses = [f"TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE) >= {float(min_value)}"]
    if tag:
        # 'tags' often stored as CSV / array / JSON; TRY to match substring
        clauses.append(f"LOWER(CAST(tags AS VARCHAR)) LIKE '%{tag.lower()}%'")
    if since:
        # since can be ISO date (YYYY-MM-DD) — try parse; if not, rely on compare-as-text
        clauses.append(f"CAST(timestamp AS VARCHAR) >= '{since}'")

    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    # Project common columns if present; otherwise select all.
    try_cols = ["alpha_id", "run_id", "timestamp", "tags", "metrics"]
    cols = []
    try:
        info = con.execute(f"PRAGMA table_info('{rel}')").fetchdf()
        have = {str(n).lower() for n in info["name"]}
        for c in try_cols:
            if c in have:
                cols.append(c)
        sel = ", ".join(cols) if cols else "*"
    except Exception:
        sel = "*"

    sql = f"""
      SELECT {sel}
      FROM {rel}
      {where_sql}
    """
    df = con.execute(sql).fetchdf()

    # If we didn’t project the numeric value, add it as a convenience column
    if metric not in df.columns and "metrics" in df.columns:
        try:
            df[metric] = df["metrics"].map(
                lambda x: duckdb.sql(f"SELECT TRY_CAST(json_extract(?::JSON, '$.{metric}') AS DOUBLE)", [x]).fetchone()[0]
            )
        except Exception:
            pass

    return df


def import_csv_to_alphas(reg, csv_path: str) -> int:
    """CSV columns allowed: id?, config_hash, metrics (JSON string), tags?, timestamp?"""
    p = Path(csv_path)
    assert p.exists(), f"CSV not found: {p}"
    con = _con_for(reg)
    con.execute(
        """
    CREATE TABLE IF NOT EXISTS alphas(
      id           BIGINT,
      ts           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      config_hash  TEXT,
      metrics      TEXT,
      tags         TEXT,
      timestamp    TIMESTAMP
    );
    """
    )
    # Load CSV (DuckDB infers types; we cast metrics to TEXT to keep JSON raw)
    con.execute(f"CREATE TEMP TABLE _csv AS SELECT * FROM read_csv_auto('{p.as_posix()}')")
    # Normalize columns
    cols = [r[1].lower() for r in con.execute("PRAGMA table_info(_csv)").fetchall()]

    def has(x):
        return x in cols

    con.execute(
        f"""
    INSERT INTO alphas(id, config_hash, metrics, tags, timestamp)
    SELECT
      {"CAST(id AS BIGINT)" if has("id") else "NULL"},
      {"config_hash" if has("config_hash") else "NULL"},
      {"CAST(metrics AS TEXT)" if has("metrics") else "NULL"},
      {"tags" if has("tags") else "NULL"},
      {"timestamp" if has("timestamp") else "CURRENT_TIMESTAMP"}
    FROM _csv
    """
    )
    n = con.execute("SELECT COUNT(*) FROM _csv").fetchone()[0]
    con.execute("DROP TABLE _csv")
    return int(n)


def html_report(reg, *, metric: str, out_html: str) -> str:
    """Write a single HTML page with Top-10 and Summary tables for the metric."""
    import duckdb
    import pandas as pd
    from pathlib import Path

    refresh_runs_view(reg)

    # Try native API first
    top, summ = None, None
    if hasattr(reg, "rank"):
        try:
            top = reg.rank(metric=metric, top_n=10)
        except Exception:
            pass
    if hasattr(reg, "get_summary"):
        try:
            summ = reg.get_summary(metric=metric)
        except Exception:
            pass

    # Fallback to DuckDB if either failed
    if top is None or summ is None:
        con = _con_for(reg)
        candidates = ["runs_view", "runs", "alpha_runs", "registry", "alphas"]

        def has_metrics(rel):
            try:
                cols = con.execute(f"PRAGMA table_info('{rel}')").fetchdf()["name"]
                return any(str(c).lower() == "metrics" for c in cols)
            except Exception:
                return False

        names = set()
        try:
            names |= {r[0].lower() for r in con.execute("SELECT name FROM duckdb_tables()").fetchall()}
            names |= {r[0].lower() for r in con.execute("SELECT table_name FROM information_schema.views").fetchall()}
        except Exception:
            pass

        rel = next((c for c in candidates if c.lower() in names and has_metrics(c)), None)

        if rel is None:
            import pandas as pd
            top = pd.DataFrame(columns=["alpha_id","run_id","timestamp","tags",metric]) if top is None else top
            summ = pd.DataFrame(columns=["count","mean","min","max"]) if summ is None else summ
        else:
            if top is None:
                top_sql = f"""
                  SELECT
                    COALESCE(alpha_id, config_hash) AS alpha_id,
                    run_id,
                    timestamp,
                    tags,
                    TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE) AS {metric}
                  FROM {rel}
                  WHERE TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE) IS NOT NULL
                  ORDER BY {metric} DESC
                  LIMIT 10
                """
                top = con.execute(top_sql).fetchdf()

            if summ is None:
                summ_sql = f"""
                  SELECT
                    COUNT(*)::BIGINT AS count,
                    AVG(TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE)) AS mean,
                    MIN(TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE)) AS min,
                    MAX(TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE)) AS max
                  FROM {rel}
                  WHERE TRY_CAST(json_extract(metrics, '$.{metric}') AS DOUBLE) IS NOT NULL
                """
                summ = con.execute(summ_sql).fetchdf()

    def _tbl(df: pd.DataFrame) -> str:
        return df.to_html(index=False, border=0)

    html = f"""
    <html><head><meta charset="utf-8"><title>Registry Report — {metric}</title>
    <style>body{{font-family:system-ui,Segoe UI,Arial}} table{{border-collapse:collapse}}
td,th{{padding:6px 10px;border:1px solid #ddd}}</style>
    </head><body>
    <h2>Top 10 by {metric}</h2>
    {_tbl(top) if isinstance(top, pd.DataFrame) and not top.empty else "<em>No rows.</em>"}
    <h2>Summary</h2>
    {_tbl(summ) if isinstance(summ, pd.DataFrame) and not summ.empty else "<em>No rows.</em>"}
    </body></html>
    """
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html).write_text(html, encoding="utf-8")
    return out_html
