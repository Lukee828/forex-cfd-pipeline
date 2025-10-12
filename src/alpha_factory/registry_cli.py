from __future__ import annotations
import argparse
import json

# Patch analytics + schema helpers
import alpha_factory.alpha_registry_schema_v025  # noqa: F401
from alpha_factory.alpha_registry import AlphaRegistry


def _mk_reg(db: str) -> AlphaRegistry:
    sig = AlphaRegistry.__init__.__code__.co_varnames
    if "db_path" in sig:
        return AlphaRegistry(db_path=db)
    if "path" in sig:
        return AlphaRegistry(path=db)
    if "database" in sig:
        return AlphaRegistry(database=db)
    return AlphaRegistry(db)  # last resort


def _parse_metrics(s: str) -> dict:
    if not s:
        return {}
    if s.strip().startswith("{"):
        return json.loads(s)
    out = {}
    for pair in s.split(","):
        if not pair.strip():
            continue
        k, v = pair.split("=", 1)
        out[k.strip()] = float(v.strip())
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser("alpha-registry")
    p.add_argument("--db", default="data/registry.duckdb")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    r = sub.add_parser("register")
    r.add_argument("--cfg", required=True)
    r.add_argument("--metrics", required=True)
    r.add_argument("--tags", default="")
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=10)
    list_cmd.add_argument("--tag")
    b = sub.add_parser("best")
    b.add_argument("--metric", required=True)
    b.add_argument("--top", type=int, default=5)
    s = sub.add_parser("summary")
    s.add_argument("--metric", required=True)
    bk = sub.add_parser("backup")
    bk.add_argument("--retention", type=int)
    bk.add_argument("--dir")

    a = p.parse_args(argv)
    reg = _mk_reg(a.db)

    if a.cmd == "init":
        reg.ensure_schema()
        print("OK: schema ensured")
        return 0

    if a.cmd == "register":
        reg.ensure_schema()
        rid = reg.register(a.cfg, _parse_metrics(a.metrics), a.tags)
        print(rid)
        return 0

    if a.cmd == "list":
        rows = reg.list_recent(a.tag, a.limit)
        for r in rows:
            print(r)
        return 0

    if a.cmd == "best":
        import duckdb

        # Rebuild runs view directly from alphas (fresh)
        con = duckdb.connect(a.db)
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
        # Robust metric extraction (numeric or quoted)
        val = (
            "COALESCE("
            " TRY_CAST(json_extract(metrics, '$.{m}') AS DOUBLE),"
            " TRY_CAST(CAST(json_extract(metrics, '$.{m}') AS VARCHAR) AS DOUBLE)"
            " )"
        ).format(m=a.metric)
        q = f"""
        WITH base AS (
          SELECT alpha_id, run_id, timestamp, tags, {val} AS value
          FROM runs
        )
        SELECT alpha_id, run_id, timestamp, tags, value
        FROM base
        WHERE value IS NOT NULL
        ORDER BY value DESC
        LIMIT {int(a.top)}
        """
        df = con.execute(q).df()
        print(df.to_string(index=False))
        return 0

    if a.cmd == "summary":
        import duckdb

        con = duckdb.connect(a.db)
        # Ensure fresh runs view
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
        val = (
            "COALESCE("
            " TRY_CAST(json_extract(metrics, '$.{m}') AS DOUBLE),"
            " TRY_CAST(CAST(json_extract(metrics, '$.{m}') AS VARCHAR) AS DOUBLE)"
            " )"
        ).format(m=a.metric)
        q = f"""
        WITH base AS (
          SELECT alpha_id, run_id, timestamp, tags, {val} AS value
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
        WHERE value IS NOT NULL
        GROUP BY alpha_id
        ORDER BY mean DESC
        """
        df = con.execute(q).df()
        print(df.to_string(index=False))
        return 0

    if a.cmd == "backup":
        path = reg.backup(retention_days=a.retention, backup_dir=a.dir)
        print(path or "")
        return 0

    p.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
