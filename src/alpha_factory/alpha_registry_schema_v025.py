from __future__ import annotations

from pathlib import Path
import os
import duckdb


def _resolve_db_path(target) -> str:
    # Accept AlphaRegistry-like or path-like
    if hasattr(target, "__dict__"):
        for attr in ("db_path", "path", "database"):
            p = getattr(target, attr, None)
            if isinstance(p, (str, Path)) and str(p):
                return str(p)
    if isinstance(target, (str, Path)) and str(target):
        return str(target)
    return ":memory:"


def ensure_alphas_schema(target) -> None:
    """
    Ensure table 'alphas' exists in DuckDB.
    'target' can be a path string/Path or a registry-like object with
    .db_path/.path/.database.
    """
    db_path = _resolve_db_path(target)
    if db_path not in (None, "", ":memory:"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = duckdb.connect(db_path if db_path else ":memory:")
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS alphas (
              id           INTEGER,
              config_hash  TEXT,
              metrics      JSON,
              tags         TEXT,
              timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
    finally:
        con.close()
