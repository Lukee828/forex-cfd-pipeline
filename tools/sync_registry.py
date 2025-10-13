import json
import sqlite3
from pathlib import Path
from src.alpha_factory import registry


def ensure_schema(con: sqlite3.Connection):
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS factors (
            name TEXT PRIMARY KEY,
            impl TEXT,
            params TEXT,
            params_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    con.commit()


def sync_registry(db_path: Path, verbose=False):
    con = sqlite3.connect(db_path)
    ensure_schema(con)
    cur = con.cursor()

    before = set(r[0] for r in cur.execute("SELECT name FROM factors"))
    rows = []
    for name in registry.names():
        fac = registry.make(name)
        impl = type(fac).__name__
        params = getattr(fac, "__dict__", {})
        # Filter to keep it light
        clean = {k: v for k, v in params.items() if isinstance(v, (int, float, str, bool))}
        blob = {"impl": impl, **clean}
        cur.execute(
            """INSERT INTO factors(name, impl, params, params_json, created_at, updated_at)
               VALUES(?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
                   impl=excluded.impl,
                   params=excluded.params,
                   params_json=excluded.params_json,
                   updated_at=CURRENT_TIMESTAMP""",
            (name, impl, json.dumps(clean), json.dumps(blob)),
        )
        rows.append((name, impl, clean))
    con.commit()
    after = set(r[0] for r in cur.execute("SELECT name FROM factors"))
    con.close()

    delta = len(after - before)
    msg = f"Synced {len(rows)} factors ({delta} new)."
    if verbose:
        print(msg)
        for name, impl, clean in rows:
            print(f"- {name:20s} {impl:15s} {clean}")
    else:
        print(msg)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Sync alpha_factory registry to SQLite")
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    sync_registry(args.db, verbose=args.verbose)
