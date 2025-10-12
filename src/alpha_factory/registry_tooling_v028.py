from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any
import csv
import json
import pathlib

from alpha_factory.alpha_registry import AlphaRegistry


@dataclass
class ImportStats:
    rows: int
    inserted: int
    skipped: int


def _parse_metrics(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    s = (value or "").strip()
    if not s:
        return {}
    if s.startswith("{") and s.endswith("}"):
        return json.loads(s)
    out: dict[str, Any] = {}
    for part in s.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


def _norm_tags(tags: str | Iterable[str] | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = tags.split(",")
    else:
        raw = list(tags)
    norm = [t.strip() for t in raw if str(t).strip()]
    seen = set()
    out: list[str] = []
    for t in norm:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def import_csv_to_alphas(
    reg: AlphaRegistry, csv_path: str | pathlib.Path
) -> ImportStats:
    csv_path = str(csv_path)
    reg.ensure_schema()
    rows = inserted = skipped = 0
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            cfg = (row.get("config_hash") or "").strip()
            if not cfg:
                skipped += 1
                continue
            metrics = _parse_metrics(row.get("metrics", ""))
            tags = _norm_tags(row.get("tags", ""))
            reg.register(cfg, metrics, tags)
            inserted += 1
    return ImportStats(rows=rows, inserted=inserted, skipped=skipped)


def html_table(html_table: str, theme: str = "light") -> str:
    theme = (theme or "light").lower()
    if theme not in {"light", "dark"}:
        theme = "light"
    if theme == "dark":
        bg, fg, border, zebra = "#0f172a", "#e5e7eb", "#334155", "#111827"
    else:
        bg, fg, border, zebra = "#ffffff", "#111827", "#dddddd", "#f8fafc"
    style = (
        "<style>\n"
        f"body{{background:{bg};color:{fg};font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif}}\n"
        "table{border-collapse:collapse}\n"
        f"td,th{{padding:6px 10px;border:1px solid {border}}}\n"
        f"tbody tr:nth-child(even) td{{background:{zebra}}}\n"
        "</style>"
    )
    return f"<!doctype html><meta charset='utf-8'>{style}\n{html_table}\n"
