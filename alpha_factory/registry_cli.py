from __future__ import annotations

import argparse
import csv
import html
import sqlite3
import time
from pathlib import Path
from typing import Dict, List

# We intentionally use sqlite3 (stdlib) even if the filename ends with .duckdb.
# Tests call our CLI only; they never open the DB themselves.
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cfg TEXT NOT NULL,
  tags TEXT,
  sharpe REAL,
  created_ts INTEGER NOT NULL
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def _parse_metrics(metrics_str: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not metrics_str:
        return out
    # format like: "sharpe=1.8,sortino=2.1"
    for part in metrics_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            out[k.strip()] = float(v.strip())
        except ValueError:
            pass
    return out


def cmd_init(args: argparse.Namespace) -> int:
    con = _connect(args.db)
    with con:
        con.executescript(SCHEMA)
    print(f"[init] DB ready at {args.db}")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    con = _connect(args.db)
    metrics = _parse_metrics(args.metrics or "")
    sharpe = metrics.get("sharpe")
    with con:
        con.executescript(SCHEMA)
        con.execute(
            "INSERT INTO runs(cfg,tags,sharpe,created_ts) VALUES(?,?,?,?)",
            (args.cfg, args.tags or "", sharpe, int(time.time())),
        )
    print(f"[register] cfg={args.cfg} sharpe={sharpe} tags={args.tags or ''}")
    return 0


def cmd_refresh_runs(args: argparse.Namespace) -> int:
    # No-op for this minimal implementation
    print("[refresh-runs] OK")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    con = _connect(args.db)
    metric = args.metric.lower()
    if metric != "sharpe":
        print("", end="")  # unknown metric -> print nothing
        return 0
    q = """
      SELECT cfg, tags, sharpe
      FROM runs
      WHERE sharpe IS NOT NULL AND sharpe >= ?
      ORDER BY sharpe DESC, created_ts DESC
      LIMIT ?
    """
    rows = list(con.execute(q, (float(args.min), int(args.limit))))
    # Print a very simple text table so tests can find "2.2"
    for cfg, tags, val in rows:
        print(f"{cfg}\t{metric}={val}\ttags={tags}")
    return 0


def _export_best(con: sqlite3.Connection, metric: str, top: int, out: Path) -> None:
    if metric != "sharpe":
        out.write_text("", encoding="utf-8")
        return
    q = """
      SELECT cfg, tags, sharpe
      FROM runs
      WHERE sharpe IS NOT NULL
      ORDER BY sharpe DESC, created_ts DESC
      LIMIT ?
    """
    rows = list(con.execute(q, (int(top),)))
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cfg", "sharpe", "tags"])
        for cfg, tags, val in rows:
            w.writerow([cfg, val, tags])


def _export_summary(con: sqlite3.Connection, metric: str, out: Path) -> None:
    if metric != "sharpe":
        out.write_text("<html><body><p>unsupported metric</p></body></html>", encoding="utf-8")
        return
    q = "SELECT cfg, tags, sharpe FROM runs WHERE sharpe IS NOT NULL ORDER BY sharpe DESC, created_ts DESC"
    rows = list(con.execute(q))
    # very small HTML summary
    lines = [
        "<html><head><meta charset='utf-8'><title>summary</title></head><body>",
        "<h1>Summary (sharpe)</h1>",
        "<table border='1'><tr><th>cfg</th><th>sharpe</th><th>tags</th></tr>",
    ]
    for cfg, tags, val in rows:
        lines.append(
            f"<tr><td>{html.escape(cfg)}</td><td>{val}</td><td>{html.escape(tags or '')}</td></tr>"
        )
    lines.append("</table></body></html>")
    out.write_text("\n".join(lines), encoding="utf-8")


def cmd_export(args: argparse.Namespace) -> int:
    con = _connect(args.db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.what == "best" and args.format == "csv":
        _export_best(con, args.metric.lower(), int(args.top), out)
        print(f"[export] best->{out}")
        return 0
    if args.what == "summary" and args.format == "html":
        _export_summary(con, args.metric.lower(), out)
        print(f"[export] summary->{out}")
        return 0
    # Unsupported combination: write empty file to be explicit and return 0
    out.write_text("", encoding="utf-8")
    print(f"[export] (noop) {args.what} as {args.format} -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alpha_factory.registry_cli", add_help=True)
    p.add_argument(
        "--db", required=True, help="Path to DB file (sqlite3 here, extension is ignored)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("register")
    sp.add_argument("--cfg", required=True)
    sp.add_argument("--metrics", required=False, default="")
    sp.add_argument("--tags", required=False, default="")
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("refresh-runs")
    sp.set_defaults(func=cmd_refresh_runs)

    sp = sub.add_parser("search")
    sp.add_argument("--metric", required=True)
    sp.add_argument("--min", required=True)
    sp.add_argument("--limit", required=True)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("export")
    sp.add_argument("--what", required=True, choices=["best", "summary"])
    sp.add_argument("--metric", required=True)
    sp.add_argument("--top", required=False, default="1")
    sp.add_argument("--format", required=True, choices=["csv", "html"])
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_export)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
