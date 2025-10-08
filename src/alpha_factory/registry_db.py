from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

DEFAULT_DB = os.path.join(os.getcwd(), ".data", "alpha_registry.db")


@dataclass(frozen=True)
class DBConfig:
    path: str = DEFAULT_DB


def get_connection(path: Optional[str] = None) -> sqlite3.Connection:
    db = path or DEFAULT_DB
    os.makedirs(os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS factors (
            name TEXT PRIMARY KEY,
            params_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TIMESTAMP DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS factors_updated_at
        AFTER UPDATE ON factors
        BEGIN
            UPDATE factors
            SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE name = NEW.name;
        END;
        """
    )
    conn.commit()


def upsert_factor(conn: sqlite3.Connection, name: str, params: dict) -> None:
    params_json = json.dumps(params, sort_keys=True)
    conn.execute(
        """
        INSERT INTO factors(name, params_json)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET params_json=excluded.params_json;
        """,
        (name, params_json),
    )
    conn.commit()


def list_factors(conn: sqlite3.Connection) -> Sequence[Tuple[str, dict]]:
    rows = conn.execute(
        "SELECT name, params_json FROM factors ORDER BY name"
    ).fetchall()
    return [(name, json.loads(pj)) for (name, pj) in rows]


def delete_factor(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("DELETE FROM factors WHERE name = ?", (name,))
    conn.commit()
    return cur.rowcount


def clear_all(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM factors;")
    conn.commit()


def sync_from_registry(registry, conn: sqlite3.Connection) -> int:
    """
    Registry → DB mirror. Returns number of upserts performed.
    `registry` is the module object with `names()` and `make()`.
    """
    init_db(conn)
    count = 0
    for name in registry.names():
        fac = registry.make(name)
        params = {}
        # Collect simple public attributes to help observability
        for a in (
            "__class__",
            "name",
            "fast",
            "slow",
            "n",
            "lookback",
            "lower",
            "upper",
        ):
            if hasattr(fac, a) and not a.startswith("__"):
                try:
                    v = getattr(fac, a)
                    if not callable(v):
                        params[a] = v
                except Exception:
                    pass
        params["__classname__"] = fac.__class__.__name__
        upsert_factor(conn, name, params)
        count += 1
    return count
