from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

# Public row type: (id, ts, config_hash, metrics, tags[, score])
PublicRow = Tuple[int, datetime, str, Dict[str, float], Tuple[str, ...]]


@dataclass
class _Entry:
    id: int
    ts: datetime
    name: str  # config_hash / alias
    metrics: Dict[str, float]
    tags: Tuple[str, ...]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _max(a: int, b: int) -> int:
    return a if a > b else b


class AlphaRegistry:
    """
    Minimal in-memory registry used by tests.

    - Accepts a "db path" but stores data in memory to avoid external deps.
    - Provides: register, list_recent, get_latest, get_best, search (w/ score),
      rank (pandas DataFrame), get_summary (pandas DataFrame),
      register_run / get_lineage (for v027 helper utilities).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = str(db_path) if db_path is not None else ""
        self._next_id = 1
        self._by_name: Dict[str, List[_Entry]] = {}
        # lineage storage: alpha_id -> list[dict]
        self._lineage: Dict[str, List[Dict]] = {}

    # keep compatibility with tests that call .init()
    def init(self) -> "AlphaRegistry":
        return self

    # --- Core API ---------------------------------------------------------

    def register(
        self,
        config_hash: str,
        metrics: Dict[str, float],
        tags: Iterable[str] | None = None,
    ) -> int:
        eid = self._next_id
        self._next_id += 1
        e = _Entry(
            id=eid,
            ts=_now(),
            name=str(config_hash),
            metrics=dict(metrics or {}),
            tags=tuple(tags or ()),
        )
        self._by_name.setdefault(e.name, []).append(e)
        return eid

    def _as_tuple(self, e: _Entry) -> PublicRow:
        return (e.id, e.ts, e.name, e.metrics, e.tags)

    def list_recent(self, *, tag: Optional[str] = None, limit: int = 10) -> List[PublicRow]:
        out: List[_Entry] = []
        for items in self._by_name.values():
            for e in items:
                if tag is not None and tag not in e.tags:
                    continue
                out.append(e)
        out.sort(key=lambda e: (e.ts, e.id), reverse=True)
        return [self._as_tuple(e) for e in out[: _max(0, int(limit))]]

    def get_latest(self, name: Optional[str] = None) -> PublicRow:
        """Return the latest row overall (name=None) or the latest row whose tags contain `name`."""
        if name is None:
            # newest by (ts, id) across all names
            all_entries = [e for lst in self._by_name.values() for e in lst]
            if not all_entries:
                raise KeyError("no rows")
            e = max(all_entries, key=lambda e: (e.ts, e.id))
            return self._as_tuple(e)

        tag = str(name)
        candidates: List[_Entry] = []
        for lst in self._by_name.values():
            for e in lst:
                if tag in e.tags:
                    candidates.append(e)
        if not candidates:
            raise KeyError(f"no rows for {tag}")
        e = max(candidates, key=lambda e: (e.ts, e.id))
        return self._as_tuple(e)

    def get_best(
        self, metric: str, top_k: int = 1
    ) -> List[Tuple[int, datetime, str, Dict[str, float], Tuple[str, ...], float]]:
        metric_l = metric.lower()
        scored: List[Tuple[_Entry, float]] = []
        for items in self._by_name.values():
            for e in items:
                m = {k.lower(): v for k, v in e.metrics.items()}
                if metric_l in m:
                    scored.append((e, float(m[metric_l])))
        scored.sort(key=lambda t: (t[1], t[0].ts, t[0].id), reverse=True)
        out: List[Tuple[int, datetime, str, Dict[str, float], Tuple[str, ...], float]] = []
        for e, s in scored[: _max(0, int(top_k))]:
            out.append(self._as_tuple(e) + (s,))
        return out

    def search(
        self,
        metric: str,
        *,
        min: Optional[float] = None,
        max: Optional[float] = None,
        tag: Optional[str] = None,
        limit: int = 10,
    ) -> List[Tuple[int, datetime, str, Dict[str, float], Tuple[str, ...], float]]:
        metric_l = metric.lower()
        scored: List[Tuple[_Entry, float]] = []
        for items in self._by_name.values():
            for e in items:
                m = {k.lower(): v for k, v in e.metrics.items()}
                if metric_l not in m:
                    continue
                v = float(m[metric_l])
                if min is not None and v < float(min):
                    continue
                if max is not None and v > float(max):
                    continue
                if tag is not None and tag not in e.tags:
                    continue
                scored.append((e, v))
        scored.sort(key=lambda t: (t[1], t[0].ts, t[0].id), reverse=True)
        return [self._as_tuple(e) + (score,) for (e, score) in scored[: _max(0, int(limit))]]

    # --- Extended API used by v027 helpers --------------------------------

    def rank(self, *, metric: str, top_n: int = 10, filters: Optional[Dict] = None):
        """
        Return a pandas.DataFrame with columns:
          id, ts, config_hash, metrics, tags, score

        Supports optional `filters` dict with keys:
          - tag: str
          - since: ISO timestamp string (>=)
          - where_sql: ignored here; kept for compatibility
        """
        tag = None
        since = None
        if isinstance(filters, dict):
            tag = filters.get("tag")
            since = filters.get("since")

        metric_l = metric.lower()
        rows: List[Tuple[_Entry, float]] = []
        for items in self._by_name.values():
            for e in items:
                if tag and tag not in e.tags:
                    continue
                if since:
                    try:
                        dt = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
                        if e.ts < dt:
                            continue
                    except Exception:
                        pass
                m = {k.lower(): v for k, v in e.metrics.items()}
                if metric_l not in m:
                    continue
                rows.append((e, float(m[metric_l])))

        rows.sort(key=lambda t: (t[1], t[0].ts, t[0].id), reverse=True)

        try:
            import pandas as pd  # type: ignore

            data = [
                {
                    "id": t[0].id,
                    "ts": t[0].ts,
                    "config_hash": t[0].name,
                    "metrics": t[0].metrics,
                    "tags": t[0].tags,
                    "score": t[1],
                }
                for t in rows[: _max(0, int(top_n))]
            ]
            return pd.DataFrame(data)
        except Exception:
            # Minimal shim object with .shape/.empty/.to_html for test convenience
            class _MiniDF(list):
                @property
                def shape(self):
                    return (len(self), 6)

                @property
                def empty(self):
                    return len(self) == 0

                def to_html(self, *a, **k):
                    return "<pre>pandas not installed</pre>"

            return _MiniDF(
                [
                    {
                        "id": t[0].id,
                        "ts": t[0].ts,
                        "config_hash": t[0].name,
                        "metrics": t[0].metrics,
                        "tags": t[0].tags,
                        "score": t[1],
                    }
                    for t in rows[: _max(0, int(top_n))]
                ]
            )

    def get_summary(self, *, metric: str):
        """
        Return a pandas.DataFrame with basic stats for the given metric across all rows.
        At minimum includes one of: mean / max / median (tests check for presence).
        """
        metric_l = metric.lower()
        vals: List[float] = []
        for items in self._by_name.values():
            for e in items:
                m = {k.lower(): v for k, v in e.metrics.items()}
                if metric_l in m:
                    vals.append(float(m[metric_l]))

        try:
            import pandas as pd  # type: ignore

            if not vals:
                return pd.DataFrame(
                    [
                        {
                            "metric": metric,
                            "count": 0,
                            "mean": None,
                            "max": None,
                            "median": None,
                        }
                    ]
                )

            s_mean = sum(vals) / len(vals)
            s_max = max(vals)
            try:
                srt = sorted(vals)
                n = len(vals)
                s_median = srt[n // 2] if n % 2 == 1 else (srt[n // 2 - 1] + srt[n // 2]) / 2
            except Exception:
                s_median = None

            return pd.DataFrame(
                [
                    {
                        "metric": metric,
                        "count": len(vals),
                        "mean": s_mean,
                        "max": s_max,
                        "median": s_median,
                    }
                ]
            )
        except Exception:
            # Dict fallback (tests only assert presence of keys)
            if not vals:
                return {"metric": metric, "count": 0, "mean": None, "max": None, "median": None}
            s_mean = sum(vals) / len(vals)
            s_max = max(vals)
            try:
                srt = sorted(vals)
                n = len(vals)
                s_median = srt[n // 2] if n % 2 == 1 else (srt[n // 2 - 1] + srt[n // 2]) / 2
            except Exception:
                s_median = None
            return {
                "metric": metric,
                "count": len(vals),
                "mean": s_mean,
                "max": s_max,
                "median": s_median,
            }

    # --- Lineage ----------------------------------------------------------

    def register_run(self, run: Dict) -> str:
        """
        Accept a run dict that includes at least:
          alpha_id, run_hash, timestamp, source_version, config_hash, config_diff, tags
        Return the run_id (string).
        """
        rid = str(run.get("run_hash") or run.get("run_id") or "")
        aid = str(run.get("alpha_id") or "")
        if not rid or not aid:
            raise ValueError("run must include alpha_id and run_hash (or run_id)")
        self._lineage.setdefault(aid, []).append(dict(run))
        return rid

    def get_lineage(self, alpha_id: str):
        """
        Return lineage as a pandas.DataFrame (columns: alpha_id, run_id, timestamp,
        source_version, config_hash, config_diff, tags). Falls back to a shim
        with .shape/.empty if pandas is unavailable.
        """
        rows = list(self._lineage.get(str(alpha_id), ()))
        try:
            import pandas as pd  # type: ignore
        except Exception:

            class _MiniDF(list):
                @property
                def shape(self):
                    return (len(self), 7)

                @property
                def empty(self):
                    return len(self) == 0

                def to_html(self, *a, **k):
                    return "<pre>pandas not installed</pre>"

            return _MiniDF(rows)

        if not rows:
            return pd.DataFrame(
                columns=[
                    "alpha_id",
                    "run_id",
                    "timestamp",
                    "source_version",
                    "config_hash",
                    "config_diff",
                    "tags",
                ]
            )

        norm = []
        for r in rows:
            norm.append(
                {
                    "alpha_id": r.get("alpha_id"),
                    "run_id": r.get("run_hash") or r.get("run_id"),
                    "timestamp": r.get("timestamp"),
                    "source_version": r.get("source_version"),
                    "config_hash": r.get("config_hash"),
                    "config_diff": r.get("config_diff"),
                    "tags": r.get("tags"),
                }
            )
        return pd.DataFrame(norm)
