"""
Validate a Parquet price library produced by the Dukascopy ingest.

Scans data/prices_* folders (or a custom root) and prints sanity stats per file:
- timeframe, symbol, bar count
- start/end timestamps (UTC)
- % zero-volume bars
- ADR median (abs(High-Low))
- duplicate timestamp count
- NaN counts per column
- weekend/holiday rough check (Sat/Sun share for intraday)

Usage:
  python -m src.data.validate_library --root data --max-files 20
"""

import argparse
import pandas as pd
import pathlib


def infer_tf_from_path(path: pathlib.Path) -> str:
    name = path.parent.name.lower()
    if "prices_1m" in name:
        return "1m"
    if "prices_5m" in name:
        return "5m"
    if "prices_1h" in name:
        return "1h"
    if "prices_1d" in name:
        return "1d"
    return "?"


def validate_file(pq: pathlib.Path) -> dict:
    df = pd.read_parquet(pq)
    # Ensure expected columns exist
    for c in ["Open", "High", "Low", "Close", "Volume", "symbol"]:
        if c not in df.columns:
            raise ValueError(f"Missing column {c} in {pq}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"Index is not DatetimeIndex in {pq}")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    bars = len(df)
    start = df.index.min()
    end = df.index.max()
    zero_vol_pct = float((df["Volume"] == 0).mean() * 100.0)
    adr = float((df["High"] - df["Low"]).abs().median())
    dupes = int(df.index.duplicated().sum())
    nans = {
        c: int(df[c].isna().sum()) for c in ["Open", "High", "Low", "Close", "Volume"]
    }

    # weekend share (intraday only)
    weekend_pct = None
    if infer_tf_from_path(pq) in ("1m", "5m", "1h"):
        weekend_pct = float((df.index.dayofweek >= 5).mean() * 100.0)

    return {
        "file": str(pq),
        "tf": infer_tf_from_path(pq),
        "symbol": pq.stem,
        "bars": bars,
        "start_utc": str(start),
        "end_utc": str(end),
        "zero_vol_pct": round(zero_vol_pct, 3),
        "adr_median": adr,
        "dup_ts": dupes,
        "nans": nans,
        "weekend_pct": None if weekend_pct is None else round(weekend_pct, 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root", default="data", help="Root folder with prices_* subfolders"
    )
    ap.add_argument(
        "--max-files", type=int, default=20, help="Limit files for quick scan"
    )
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    folders = [p for p in root.glob("prices_*") if p.is_dir()]
    if not folders:
        print(f"No prices_* folders under {root}")
        return 0

    files = []
    for f in folders:
        files.extend(sorted(f.glob("*.parquet")))
    if not files:
        print(f"No Parquet files found under {root}/prices_* ")
        return 0
    files = files[: args.max_files]

    rows = []
    for pq in files:
        try:
            rows.append(validate_file(pq))
        except Exception as e:
            rows.append({"file": str(pq), "error": str(e)})
    # Print compact table
    import json

    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
