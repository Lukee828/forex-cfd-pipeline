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
    cols = {
        str(r[1]).lower() for r in con.execute("PRAGMA table_info(alphas)").fetchall()
    }
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
) -> pd.DataFrame:
    """Return runs (alpha_id, run_id, timestamp, tags, value) where metric >= min_value."""
    refresh_runs_view(reg)
    from alpha_factory.alpha_registry import AlphaRegistry  # noqa: F401

    # Use rank() with a where_sql guard (DuckDB-safe, params via overrides)
    filters = {
        "where_sql": f"TRY_CAST(json_extract(metrics, '$.' || '{metric}') AS DOUBLE) >= {float(min_value)}"
    }
    if tag:
        filters["tag"] = tag
    if since:
        filters["since"] = since
    df = reg.rank(metric=metric, filters=filters, top_n=10_000)
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
    con.execute(
        f"CREATE TEMP TABLE _csv AS SELECT * FROM read_csv_auto('{p.as_posix()}')"
    )
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
    """Write a single HTML page with Rank(top 10) and Summary tables."""

    refresh_runs_view(reg)
    top = reg.rank(metric=metric, top_n=10)
    summ = reg.get_summary(metric=metric)

    # minimal inline HTML
    def _tbl(df: pd.DataFrame) -> str:
        return df.to_html(index=False, border=0)

    html = f"""
    <html><head><meta charset="utf-8"><title>Registry Report — {metric}</title>
    <style>body{{font-family:system-ui,Segoe UI,Arial}} table{{border-collapse:collapse}}
td,th{{padding:6px 10px;border:1px solid #ddd}}</style>
    </head><body>
    <h2>Top 10 by {metric}</h2>
    {_tbl(top) if not top.empty else "<em>No rows.</em>"}
    <h2>Summary</h2>
    {_tbl(summ) if not summ.empty else "<em>No rows.</em>"}
    </body></html>
    """
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html).write_text(html, encoding="utf-8")
    return out_html
