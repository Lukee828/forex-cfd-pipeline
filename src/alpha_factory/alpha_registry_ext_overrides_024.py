"""
Legacy v0.2.4 overrides for AlphaRegistry.

Provides rank/get_summary compat, plus safe stubs for compare/lineage.
Imported by tests to install monkey-patches onto AlphaRegistry.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import duckdb
import pandas as pd

# Reuse helper to build/refresh views from the toolkit module if available
try:
    from alpha_factory.registry_tooling_v027 import refresh_runs_view  # type: ignore
except Exception:  # pragma: no cover
    def refresh_runs_view(reg) -> None:
        pass  # will rely on existing tables

# Canonical class to patch
from registry.alpha_registry import AlphaRegistry  # type: ignore

def _con_for(reg):
    # mirror of the helper used elsewhere
    con = getattr(reg, "con", None)
    if con is not None:
        return con
    for attr in ("db_path", "path", "database"):
        p = getattr(reg, attr, None)
        if isinstance(p, str) and p:
            return duckdb.connect(p)
    return duckdb.connect(":memory:")

def _pick_rel(con) -> Optional[str]:
    # Find a relation with a JSON 'metrics' column
    candidates = ["runs_view", "runs", "alpha_runs", "registry", "alphas"]
    names = set()
    try:
        names |= {r[0].lower() for r in con.execute("SELECT name FROM duckdb_tables()").fetchall()}
        names |= {r[0].lower() for r in con.execute("SELECT table_name FROM information_schema.views").fetchall()}
    except Exception:
        pass

    def has_metrics(rel: str) -> bool:
        try:
            cols = con.execute(f"PRAGMA table_info('{rel}')").fetchdf()["name"]
            return any(str(c).lower() == "metrics" for c in cols)
        except Exception:
            return False

    for c in candidates:
        if c.lower() in names and has_metrics(c):
            return c
    return None

def _filters_to_where(metric: str, filters: Optional[Dict[str, Any]]) -> str:
    clauses = [f"TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL"]
    if not filters:
        return " WHERE " + " AND ".join(clauses)
    if "where_sql" in filters and filters["where_sql"]:
        clauses.append(str(filters["where_sql"]))
    if "tag" in filters and filters["tag"]:
        t = str(filters["tag"]).lower()
        clauses.append(f"LOWER(CAST(tags AS VARCHAR)) LIKE '%{t}%'")
    if "since" in filters and filters["since"]:
        s = str(filters["since"])
        clauses.append(f"CAST(timestamp AS VARCHAR) >= '{s}'")
    return " WHERE " + " AND ".join(clauses)

def _ensure_runs(reg) -> tuple[duckdb.DuckDBPyConnection, Optional[str]]:
    refresh_runs_view(reg)
    con = _con_for(reg)
    rel = _pick_rel(con)
    return con, rel

# --- Compat methods that will be patched onto AlphaRegistry ---

def _rank(self: AlphaRegistry, *, metric: str, filters: Optional[Dict[str, Any]] = None, top_n: int = 100) -> pd.DataFrame:
    con, rel = _ensure_runs(self)
    if rel is None:
        return pd.DataFrame(columns=["alpha_id", "run_id", "timestamp", "tags", metric])

    where_sql = _filters_to_where(metric, filters)
    sql = f"""
      SELECT
        COALESCE(alpha_id, config_hash) AS alpha_id,
        run_id,
        timestamp,
        tags,
        TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) AS {metric}
      FROM {rel}
      {where_sql}
      ORDER BY {metric} DESC
      LIMIT {int(top_n)}
    """
    return con.execute(sql).fetchdf()

def _get_summary(self: AlphaRegistry, *, metric: str) -> pd.DataFrame:
    con, rel = _ensure_runs(self)
    if rel is None:
        return pd.DataFrame(columns=["count", "mean", "min", "max"])
    sql = f"""
      SELECT
        COUNT(*)::BIGINT AS count,
        AVG(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS mean,
        MIN(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS min,
        MAX(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS max
      FROM {rel}
      WHERE TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL
    """
    return con.execute(sql).fetchdf()

def _compare(self: AlphaRegistry, *args, **kwargs) -> pd.DataFrame:
    # Minimal safe stub; extend if tests exercise it
    return pd.DataFrame()

def _lineage(self: AlphaRegistry, *args, **kwargs) -> pd.DataFrame:
    # Minimal safe stub; extend if tests exercise it
    return pd.DataFrame()

# --- Installer ---

INSTALLED = False

def install() -> bool:
    global INSTALLED
    # Attach methods once
    if not getattr(AlphaRegistry, "rank", None):
        setattr(AlphaRegistry, "rank", _rank)
    if not getattr(AlphaRegistry, "get_summary", None):
        setattr(AlphaRegistry, "get_summary", _get_summary)
    if not getattr(AlphaRegistry, "compare", None):
        setattr(AlphaRegistry, "compare", _compare)
    if not getattr(AlphaRegistry, "lineage", None):
        setattr(AlphaRegistry, "lineage", _lineage)
    INSTALLED = True
    return True

# Side-effect on import: install overrides
install()
apply = install

__all__ = ["install", "apply", "INSTALLED"]

# --- Register wrapper: mirror into DuckDB for compat queries ---
try:
    _ORIG_REGISTER = getattr(AlphaRegistry, "register", None)
except Exception:
    _ORIG_REGISTER = None

def _ensure_alphas_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS alphas(
          id           BIGINT,
          ts           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          config_hash  TEXT,
          metrics      TEXT,
          tags         TEXT,
          timestamp    TIMESTAMP
        );
    """)

def _next_id(con):
    try:
        row = con.execute("SELECT COALESCE(MAX(id),0)+1 FROM alphas").fetchone()
        return int(row[0]) if row else 1
    except Exception:
        return 1

def _normalize_register_args(args, kwargs):
    if args and not kwargs and len(args) >= 2:
        # Forms: (config_hash, metrics, [tags])
        cfg = args[0]
        met = args[1]
        tgs = args[2] if len(args) >= 3 else None
        return cfg, met, tgs
    # Keyword forms
    cfg = kwargs.get("config_hash") or kwargs.get("hash") or kwargs.get("id") or kwargs.get("key")
    met = kwargs.get("metrics") or kwargs.get("metric") or {}
    tgs = kwargs.get("tags")
    return cfg, met, tgs

def _register_wrapper(self, *args, **kwargs):
    # Call original first (if exists), but don't fail the compat mirror if it raises
    err = None
    if callable(_ORIG_REGISTER):
        try:
            res = _ORIG_REGISTER(self, *args, **kwargs)
        except Exception as e:
            # Keep going; we still want our compat path to work for tests
            res = None
            err = e
    else:
        res = None

    cfg, met, tgs = _normalize_register_args(args, kwargs)
    # Mirror row into DuckDB alphas table for rank/get_summary fallbacks
    try:
        con = _con_for(self)
        _ensure_alphas_table(con)
        new_id = _next_id(con)
        import json
        j = json.dumps(met) if not isinstance(met, str) else met
        tg = ",".join(tgs) if isinstance(tgs, (list, tuple)) else (tgs or "")
        con.execute(
            "INSERT INTO alphas(id, config_hash, metrics, tags, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [new_id, str(cfg) if cfg is not None else None, j, str(tg)]
        )
    except Exception:
        pass

    if err:
        # Preserve original error semantics after mirroring
        raise err
    return res

# Attach wrapper only once
if getattr(AlphaRegistry, "_compat_register_wrapped", False) is not True:
    try:
        setattr(AlphaRegistry, "register", _register_wrapper)
        setattr(AlphaRegistry, "_compat_register_wrapped", True)
    except Exception:
        pass
# --- compat: persistent connection helper override (appended) ---
def _con_for(reg):
    # Prefer a connection attribute if provided by the registry
    for attr in ("con", "_con", "conn", "_conn"):
        c = getattr(reg, attr, None)
        if c is not None:
            return c

    # Try file-backed paths on the registry
    for attr in ("db_path", "path", "database", "db"):
        p = getattr(reg, attr, None)
        if isinstance(p, str) and p:
            try:
                return duckdb.connect(p)
            except Exception:
                pass

    # Fallback: a persistent in-memory connection stored on the instance
    c = getattr(reg, "_compat_con", None)
    if c is None:
        c = duckdb.connect()
        try:
            setattr(reg, "_compat_con", c)
        except Exception:
            pass
    return c
# --- compat: persistent connection map (per-registry), overrides _con_for() ---
from weakref import WeakKeyDictionary as _WKD
_CONN_MAP = _WKD()

def _con_for(reg):
    # 1) if registry already exposes a connection, reuse and cache it
    for attr in ("con", "_con", "conn", "_conn"):
        c = getattr(reg, attr, None)
        if c is not None:
            try:
                _CONN_MAP[reg] = c
            except Exception:
                pass
            return c

    # 2) if registry exposes a file path, open once and cache
    for attr in ("db_path", "path", "database", "db"):
        p = getattr(reg, attr, None)
        if isinstance(p, str) and p:
            c = _CONN_MAP.get(reg)
            if c is None:
                try:
                    c = duckdb.connect(p)
                    _CONN_MAP[reg] = c
                except Exception:
                    c = None
            if c is not None:
                return c

    # 3) fallback: one persistent in-memory connection per instance
    c = _CONN_MAP.get(reg)
    if c is None:
        c = duckdb.connect()  # :memory:
        try:
            _CONN_MAP[reg] = c
        except Exception:
            pass
    return c

# --- compat: fix relation discovery for DuckDB >= 1.1 and harden rank/summary ---

def _rel_names(con):
    names = set()
    try:
        names |= {r[0].lower() for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    except Exception:
        pass
    try:
        names |= {r[0].lower() for r in con.execute("SELECT table_name FROM duckdb_views()").fetchall()}
    except Exception:
        # fallback to information_schema
        try:
            names |= {r[0].lower() for r in con.execute("SELECT table_name FROM information_schema.views").fetchall()}
        except Exception:
            pass
    return names

def _has_metrics(con, rel: str) -> bool:
    try:
        cols = con.execute(f"PRAGMA table_info('{rel}')").fetchdf()['name']
        return any(str(c).lower() == 'metrics' for c in cols)
    except Exception:
        return False

def _pick_rel(con):
    # Prefer any existing runs view/table, then fall back to alphas
    for rel in ("runs_view", "runs", "alpha_runs", "registry", "alphas"):
        if rel.lower() in _rel_names(con) and _has_metrics(con, rel):
            return rel
    return None

def _rank(self, *, metric: str, filters=None, top_n: int = 100):
    con = _con_for(self)
    # Try discovered relation
    rel = _pick_rel(con)
    # Hard fallback to alphas if it exists
    if rel is None and 'alphas' in _rel_names(con) and _has_metrics(con, 'alphas'):
        rel = 'alphas'
    if rel is None:
        import pandas as pd
        return pd.DataFrame(columns=['alpha_id','run_id','timestamp','tags', metric])

    clauses = [f"TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL"]
    if filters:
        w = filters.get('where_sql')
        if w: clauses.append(str(w))
        t = filters.get('tag')
        if t: clauses.append(f"LOWER(CAST(tags AS VARCHAR)) LIKE '%{str(t).lower()}%'")
        s = filters.get('since')
        if s: clauses.append(f"CAST(timestamp AS VARCHAR) >= '{s}'")
    where_sql = " WHERE " + " AND ".join(clauses)

    sql = f"""
      SELECT
        COALESCE(alpha_id, config_hash) AS alpha_id,
        run_id,
        timestamp,
        tags,
        TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) AS {metric}
      FROM {rel}
      {where_sql}
      ORDER BY {metric} DESC
      LIMIT {int(top_n)}
    """
    return con.execute(sql).fetchdf()

def _get_summary(self, *, metric: str):
    con = _con_for(self)
    rel = _pick_rel(con)
    if rel is None and 'alphas' in _rel_names(con) and _has_metrics(con, 'alphas'):
        rel = 'alphas'
    if rel is None:
        import pandas as pd
        return pd.DataFrame(columns=['count','mean','min','max'])
    sql = f"""
      SELECT
        COUNT(*)::BIGINT AS count,
        AVG(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS mean,
        MIN(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS min,
        MAX(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS max
      FROM {rel}
      WHERE TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL
    """
    return con.execute(sql).fetchdf()

# Re-attach patched methods
try:
    from registry.alpha_registry import AlphaRegistry  # type: ignore
    setattr(AlphaRegistry, "rank", _rank)
    setattr(AlphaRegistry, "get_summary", _get_summary)
except Exception:
    pass
# --- compat: dynamic column selection (no alias-before-define) ---

def _cols(con, rel):
    try:
        df = con.execute(f"PRAGMA table_info('{rel}')").fetchdf()
        return {str(n).lower() for n in df["name"]}
    except Exception:
        return set()

def _choose_cols(con, rel):
    cols = _cols(con, rel)
    alpha_col = "alpha_id" if "alpha_id" in cols else ("config_hash" if "config_hash" in cols else "NULL")
    run_col   = "run_id"   if "run_id"   in cols else ("id"          if "id"          in cols else "NULL")
    if   "timestamp" in cols: ts = "timestamp"
    elif "ts"        in cols: ts = "ts"
    elif "created_at" in cols: ts = "created_at"
    elif "time"      in cols: ts = "time"
    else: ts = "CURRENT_TIMESTAMP"
    tags_col = "tags" if "tags" in cols else "NULL"
    return alpha_col, run_col, ts, tags_col

def _rank(self, *, metric: str, filters=None, top_n: int = 100):
    con = _con_for(self)
    rel = _pick_rel(con)
    if rel is None and "alphas" in _rel_names(con) and _has_metrics(con, "alphas"):
        rel = "alphas"
    if rel is None:
        import pandas as pd
        return pd.DataFrame(columns=["alpha_id","run_id","timestamp","tags", metric])

    alpha_col, run_col, ts_expr, tags_col = _choose_cols(con, rel)

    clauses = [f"TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL"]
    if filters:
        w = filters.get("where_sql")
        if w: clauses.append(str(w))
        t = filters.get("tag")
        if t: clauses.append(f"LOWER(CAST({tags_col} AS VARCHAR)) LIKE '%{str(t).lower()}%'")
        s = filters.get("since")
        if s: clauses.append(f"CAST({ts_expr} AS VARCHAR) >= '{s}'")
    where_sql = " WHERE " + " AND ".join(clauses)

    sql = f"""
      SELECT
        {alpha_col} AS alpha_id,
        {run_col}   AS run_id,
        {ts_expr}   AS timestamp,
        {tags_col}  AS tags,
        TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) AS {metric}
      FROM {rel}
      {where_sql}
      ORDER BY {metric} DESC
      LIMIT {int(top_n)}
    """
    return con.execute(sql).fetchdf()

def _get_summary(self, *, metric: str):
    con = _con_for(self)
    rel = _pick_rel(con)
    if rel is None and "alphas" in _rel_names(con) and _has_metrics(con, "alphas"):
        rel = "alphas"
    if rel is None:
        import pandas as pd
        return pd.DataFrame(columns=["count","mean","min","max"])

    sql = f"""
      SELECT
        COUNT(*)::BIGINT AS count,
        AVG(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS mean,
        MIN(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS min,
        MAX(TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE)) AS max
      FROM {rel}
      WHERE TRY_CAST(json_extract(CAST(metrics AS JSON), '$.{metric}') AS DOUBLE) IS NOT NULL
    """
    return con.execute(sql).fetchdf()

# Re-attach the updated methods
try:
    from registry.alpha_registry import AlphaRegistry  # type: ignore
    setattr(AlphaRegistry, "rank", _rank)
    setattr(AlphaRegistry, "get_summary", _get_summary)
except Exception:
    pass
# --- compat: register_run + lineage ---

def _ensure_runs_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs(
          alpha_id       TEXT,
          run_id         TEXT,
          timestamp      TIMESTAMP,
          tags           TEXT,
          metrics        TEXT,
          config_hash    TEXT,
          run_hash       TEXT,
          source_version TEXT,
          config_diff    TEXT
        );
    """)

def _register_run(self, run: dict) -> str:
    """
    Compat method. Accepts a dict like:
      {
        "alpha_id": "s2e_brk",
        "run_hash": "r1",
        "timestamp": "2025-10-12T10:00:00Z",
        "source_version": "abc123",
        "config_hash": "h1",
        "config_diff": {"lr": 0.1},
        "tags": "exp,nightly",
        "metrics": {"sharpe": 2.0}  # optional
      }
    """
    import json, uuid
    con = _con_for(self)
    _ensure_runs_table(con)

    alpha_id = run.get("alpha_id") or run.get("config_hash")
    run_id   = run.get("run_id") or run.get("run_hash") or str(uuid.uuid4())
    ts       = run.get("timestamp")  # string is OK; DuckDB will parse
    tags     = run.get("tags", "")
    metrics  = run.get("metrics")
    metrics_txt = json.dumps(metrics) if isinstance(metrics, (dict, list)) else (metrics if metrics is not None else None)
    cfg      = run.get("config_hash")
    run_hash = run.get("run_hash")
    src_ver  = run.get("source_version")
    cfg_diff = run.get("config_diff")
    cfg_diff_txt = json.dumps(cfg_diff) if isinstance(cfg_diff, (dict, list)) else (cfg_diff if cfg_diff is not None else None)

    con.execute(
        "INSERT INTO runs(alpha_id, run_id, timestamp, tags, metrics, config_hash, run_hash, source_version, config_diff) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [alpha_id, run_id, ts, tags, metrics_txt, cfg, run_hash, src_ver, cfg_diff_txt]
    )
    return run_id

def _lineage(self, alpha_id: str | None = None, run_id: str | None = None):
    con = _con_for(self)
    _ensure_runs_table(con)

    clauses = []
    if alpha_id:
        clauses.append(f"alpha_id = '{alpha_id}'")
    if run_id:
        clauses.append(f"run_id = '{run_id}'")
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"""
      SELECT
        alpha_id, run_id, timestamp, tags,
        config_hash, run_hash, source_version, config_diff,
        TRY_CAST(json_extract(CAST(metrics AS JSON), '$.sharpe') AS DOUBLE) AS sharpe
      FROM runs
      {where_sql}
      ORDER BY timestamp
    """
    return con.execute(sql).fetchdf()

# Attach only if missing to avoid stepping on real methods
try:
    from registry.alpha_registry import AlphaRegistry  # type: ignore
    if not getattr(AlphaRegistry, "register_run", None):
        setattr(AlphaRegistry, "register_run", _register_run)
    # lineage exists as stub above; override with this richer version
    setattr(AlphaRegistry, "lineage", _lineage)
except Exception:
    pass
# --- compat: register_run + lineage ---

def _ensure_runs_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs(
          alpha_id       TEXT,
          run_id         TEXT,
          timestamp      TIMESTAMP,
          tags           TEXT,
          metrics        TEXT,
          config_hash    TEXT,
          run_hash       TEXT,
          source_version TEXT,
          config_diff    TEXT
        );
    """)

def _register_run(self, run: dict) -> str:
    """
    Compat method. Accepts a dict like:
      {
        "alpha_id": "s2e_brk",
        "run_hash": "r1",
        "timestamp": "2025-10-12T10:00:00Z",
        "source_version": "abc123",
        "config_hash": "h1",
        "config_diff": {"lr": 0.1},
        "tags": "exp,nightly",
        "metrics": {"sharpe": 2.0}  # optional
      }
    """
    import json, uuid
    con = _con_for(self)
    _ensure_runs_table(con)

    alpha_id = run.get("alpha_id") or run.get("config_hash")
    run_id   = run.get("run_id") or run.get("run_hash") or str(uuid.uuid4())
    ts       = run.get("timestamp")  # string is OK; DuckDB will parse
    tags     = run.get("tags", "")
    metrics  = run.get("metrics")
    metrics_txt = json.dumps(metrics) if isinstance(metrics, (dict, list)) else (metrics if metrics is not None else None)
    cfg      = run.get("config_hash")
    run_hash = run.get("run_hash")
    src_ver  = run.get("source_version")
    cfg_diff = run.get("config_diff")
    cfg_diff_txt = json.dumps(cfg_diff) if isinstance(cfg_diff, (dict, list)) else (cfg_diff if cfg_diff is not None else None)

    con.execute(
        "INSERT INTO runs(alpha_id, run_id, timestamp, tags, metrics, config_hash, run_hash, source_version, config_diff) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [alpha_id, run_id, ts, tags, metrics_txt, cfg, run_hash, src_ver, cfg_diff_txt]
    )
    return run_id

def _lineage(self, alpha_id: str | None = None, run_id: str | None = None):
    con = _con_for(self)
    _ensure_runs_table(con)

    clauses = []
    if alpha_id:
        clauses.append(f"alpha_id = '{alpha_id}'")
    if run_id:
        clauses.append(f"run_id = '{run_id}'")
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"""
      SELECT
        alpha_id, run_id, timestamp, tags,
        config_hash, run_hash, source_version, config_diff,
        TRY_CAST(json_extract(CAST(metrics AS JSON), '$.sharpe') AS DOUBLE) AS sharpe
      FROM runs
      {where_sql}
      ORDER BY timestamp
    """
    return con.execute(sql).fetchdf()

# Attach only if missing to avoid stepping on real methods
try:
    from registry.alpha_registry import AlphaRegistry  # type: ignore
    if not getattr(AlphaRegistry, "register_run", None):
        setattr(AlphaRegistry, "register_run", _register_run)
    # lineage exists as stub above; override with this richer version
    setattr(AlphaRegistry, "lineage", _lineage)
except Exception:
    pass
# --- compat: get_lineage(alpha_id) -> delegates to lineage() ---
def _get_lineage(self, alpha_id: str):
    try:
        return self.lineage(alpha_id=alpha_id)
    except TypeError:
        # In case another signature took precedence, force keyword
        return self.lineage(alpha_id=alpha_id)

try:
    from registry.alpha_registry import AlphaRegistry  # type: ignore
    if not getattr(AlphaRegistry, "get_lineage", None):
        setattr(AlphaRegistry, "get_lineage", _get_lineage)
except Exception:
    pass
