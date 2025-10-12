from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import duckdb
import json


class AlphaRegistry:
    """
    Minimal registry for alpha runs.

    Storage (DuckDB):
      table alphas(
        id BIGINT PRIMARY KEY,     -- portable; managed by us
        ts TIMESTAMP NOT NULL DEFAULT now(),
        config_hash TEXT NOT NULL,
        metrics TEXT NOT NULL,     -- JSON string
        tags TEXT NOT NULL         -- comma-separated, sorted & deduped
      )
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    # ---- lifecycle ----
    def init(self) -> "AlphaRegistry":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(self.db_path))
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

        con = duckdb.connect(str(self.db_path))
        try:
            con.execute("BEGIN")
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
        con = duckdb.connect(str(self.db_path))
        try:
            rows = con.execute(
                f"""
                SELECT
                  id, ts, config_hash, metrics, tags,
                  CAST(json_extract(metrics, '$."{metric}"') AS DOUBLE) AS score
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
        """
        Return recent rows (id, ts, config_hash, metrics, tags), newest first.
        If 'tag' is provided, filter by substring match within tags list.
        """
        con = duckdb.connect(str(self.db_path))
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
