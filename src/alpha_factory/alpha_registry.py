from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import duckdb


class AlphaRegistry:
    """
    Minimal registry for alpha runs (DuckDB).
    Table: alphas(id BIGINT PK, ts TIMESTAMP, config_hash TEXT, metrics TEXT(JSON), tags TEXT)
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    # Optional initializer if callers want to pre-create schema
    def init(self) -> "AlphaRegistry":
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(self.db_path)
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS alphas (
                  id BIGINT PRIMARY KEY,
                  ts TIMESTAMP NOT NULL DEFAULT now(),
                  config_hash TEXT NOT NULL,
                  metrics TEXT NOT NULL,
                  tags TEXT NOT NULL
                );
                """
            )
        finally:
            con.close()
        return self

    # Internal helper to ensure schema *inside* transactions
    def _ensure_schema(self, con) -> None:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS alphas (
              id BIGINT PRIMARY KEY,
              ts TIMESTAMP NOT NULL DEFAULT now(),
              config_hash TEXT NOT NULL,
              metrics TEXT NOT NULL,
              tags TEXT NOT NULL
            );
            """
        )

    # ---- writes ----
    def register(
        self,
        config_hash: str,
        metrics: dict[str, Any],
        tags: Iterable[str] | None = None,
    ) -> int:
        """Insert a run; returns generated id."""
        tags = tags or []
        tags_s = ",".join(sorted(set(str(t).strip() for t in tags if str(t).strip())))
        mjson = json.dumps(metrics or {}, sort_keys=True, separators=(",", ":"))

        con = duckdb.connect(self.db_path)
        try:
            con.execute("BEGIN")
            self._ensure_schema(con)  # make the table if missing
            next_id = con.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM alphas;"
            ).fetchone()[0]
            rid = con.execute(
                "INSERT INTO alphas (id, config_hash, metrics, tags) VALUES (?, ?, ?, ?) RETURNING id;",
                [int(next_id), config_hash, mjson, tags_s],
            ).fetchone()[0]
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return int(rid)

    # ---- reads ----
    def get_best(self, metric: str, n: int = 1) -> list[tuple]:
        """
        Return top-n rows ordered by the JSON metric (desc), with a computed 'score' column last.
        Row columns: (id, ts, config_hash, metrics, tags, score)
        """
        con = duckdb.connect(self.db_path)
        try:
            rows = con.execute(
                f"""
                SELECT
                  id, ts, config_hash, metrics, tags,
                  CAST(json_extract(metrics, '$.{metric}') AS DOUBLE) AS score
                FROM alphas
                ORDER BY score DESC NULLS LAST, id ASC
                LIMIT ?;
                """,
                [n],
            ).fetchall()
        finally:
            con.close()
        return list(rows)

    def list_recent(self, tag: str | None = None, limit: int = 10) -> list[tuple]:
        """Return recent rows (id, ts, config_hash, metrics, tags), newest first."""
        con = duckdb.connect(self.db_path)
        try:
            if tag:
                rows = con.execute(
                    """
                    SELECT id, ts, config_hash, metrics, tags
                    FROM alphas
                    WHERE position(? in tags) > 0
                    ORDER BY ts DESC, id DESC
                    LIMIT ?;
                    """,
                    [tag, limit],
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT id, ts, config_hash, metrics, tags
                    FROM alphas
                    ORDER BY ts DESC, id DESC
                    LIMIT ?;
                    """,
                    [limit],
                ).fetchall()
        finally:
            con.close()
        return list(rows)

    def get_latest(self, tag: str | None = None) -> tuple | None:
        """Return newest row (id, ts, config_hash, metrics, tags)."""
        con = duckdb.connect(self.db_path)
        try:
            if tag:
                q = """
                SELECT id, ts, config_hash, metrics, tags
                FROM alphas
                WHERE position(? in tags) > 0
                ORDER BY ts DESC, id DESC
                LIMIT 1;
                """
                rows = con.execute(q, [tag]).fetchall()
            else:
                q = """
                SELECT id, ts, config_hash, metrics, tags
                FROM alphas
                ORDER BY ts DESC, id DESC
                LIMIT 1;
                """
                rows = con.execute(q).fetchall()
            return rows[0] if rows else None
        finally:
            con.close()

    def search(
        self,
        metric: str,
        min: float | None = None,
        max: float | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[tuple]:
        """
        Return rows (id, ts, config_hash, metrics, tags, score) where
        score = CAST(json_extract(metrics, '$.{metric}') AS DOUBLE).
        Optional bounds: min/max. Optional tag substring filter.
        Ordered by score DESC NULLS LAST, ts DESC, id DESC.
        """
        con = duckdb.connect(self.db_path)
        try:
            clauses: list[str] = []
            params: list[object] = []

            score_expr = f"CAST(json_extract(metrics, '$.{metric}') AS DOUBLE)"

            if min is not None:
                clauses.append(score_expr + " >= ?")
                params.append(float(min))
            if max is not None:
                clauses.append(score_expr + " <= ?")
                params.append(float(max))
            if tag:
                clauses.append("position(? in tags) > 0")
                params.append(tag)

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"""
                SELECT id, ts, config_hash, metrics, tags, {score_expr} AS score
                FROM alphas
                {where_sql}
                ORDER BY score DESC NULLS LAST, ts DESC, id DESC
                LIMIT ?
            """
            params.append(int(limit))
            return con.execute(sql, params).fetchall()
        finally:
            con.close()


# --- Back-compat for older CLI/tests ---
# Expose public ensure_schema() that delegates to the internal method.
try:
    # If the attribute doesn't exist, hasattr==False
    pass
finally:
    if not hasattr(AlphaRegistry, "ensure_schema"):
        AlphaRegistry.ensure_schema = AlphaRegistry._ensure_schema


# --- Back-compat: public ensure_schema() that manages its own connection
def _compat_ensure_schema(self):
    import duckdb

    con = duckdb.connect(str(self.db_path))
    try:
        self._ensure_schema(con)
    finally:
        con.close()


# Expose as public method expected by older CLI/tests
AlphaRegistry.ensure_schema = _compat_ensure_schema
