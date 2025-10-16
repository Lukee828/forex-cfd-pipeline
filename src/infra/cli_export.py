from __future__ import annotations
import argparse
import os
from pathlib import Path
from datetime import datetime, timezone
import duckdb

# Local infra
from src.infra.export_features import export_risk_snapshot, RiskInputs

def _ts():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def main():
    ap = argparse.ArgumentParser(description="Export risk feature snapshots to DuckDB and Parquet.")
    ap.add_argument("--pairs", default=os.getenv("PAIRS", "EURUSD,GBPUSD"),
                    help="Comma-separated FX pairs (default from PAIRS env).")
    ap.add_argument("--db", default=os.getenv("FS_DB", "./fs.duckdb"),
                    help="DuckDB path (default ./fs.duckdb or FS_DB env).")
    ap.add_argument("--parquet", default=os.getenv("FS_PARQUET_DIR", "./artifacts/exports"),
                    help="Folder for Parquet snapshots (default ./artifacts/exports or FS_PARQUET_DIR env).")
    ap.add_argument("--spread-bps", type=float, default=float(os.getenv("SPREAD_BPS", "18.0")),
                    help="Synthetic spread bps for snapshot (default 18).")
    args = ap.parse_args()

    db_path = Path(args.db)
    pq_dir = Path(args.parquet)
    pq_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    # housekeeping; safe no-ops if tiny DB
    con.execute("PRAGMA optimize;")

    wrote = []
    for pair in [p.strip() for p in args.pairs.split(",") if p.strip()]:
        tbl = export_risk_snapshot(RiskInputs(pair=pair, spread_bps=args.spread_bps), db_path=str(db_path))
        # export the newest row for this pair to partitioned parquet
        ts = _ts()
        outdir = pq_dir / f"pair={pair}"
        outdir.mkdir(parents=True, exist_ok=True)
        outfile = outdir / f"snapshot-{ts}.parquet"
        con.execute(f"COPY (SELECT * FROM {tbl} WHERE pair = ? ORDER BY ts DESC LIMIT 1) "
                    f"TO ? (FORMAT PARQUET)", [pair, str(outfile)])
        wrote.append(str(outfile))

    print(f"[export] DB={db_path} files={len(wrote)}")
    for w in wrote:
        print(f"  - {w}")

if __name__ == "__main__":
    main()