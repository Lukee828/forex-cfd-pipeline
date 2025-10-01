"""
Batch ingest a folder of Dukascopy-style CSVs into Parquet by (symbol, timeframe).

Examples of recognized filenames (case-insensitive):
  EURUSD_1m.csv, eurusd-M1.csv, XAUUSD_H1.csv, us500-5m-2021.csv
Also works if symbols are folder names and files are generic:
  data/EURUSD/*.csv  -> symbol=EURUSD (derived from parent)
Timeframe tokens recognized: M1, 1m, 5m, M5, H1, 1h, D1, 1d

Usage:
  python -m src.data.batch_ingest --src /path/to/csv_root --out data --default-tf 1h

It calls the same normalization/resampling helpers as the dukascopy_downloader module.
"""

import argparse
import pandas as pd
import pathlib
import re
from .dukascopy_downloader import _normalize, _resample, _save_parquet

TF_MAP = {
    "1m": "1m",
    "m1": "1m",
    "5m": "5m",
    "m5": "5m",
    "1h": "1h",
    "h1": "1h",
    "1d": "1d",
    "d1": "1d",
}


def infer_symbol_and_tf(path: pathlib.Path, default_tf: str) -> tuple[str, str]:
    name = path.name.lower()
    # Infer tf from filename tokens
    tf = None
    for token, tfv in TF_MAP.items():
        if re.search(rf"(^|[^a-z0-9]){token}([^a-z0-9]|$)", name):
            tf = tfv
            break
    if tf is None:
        tf = default_tf

    # Infer symbol: filename prefix before first '_' or '-', else parent folder
    symbol = None
    m = re.match(r"^([a-z0-9]+)[\-_]", name)
    if m:
        symbol = m.group(1).upper()
    else:
        symbol = path.parent.name.upper()
    symbol = symbol.replace(".CSV", "").upper()
    return symbol, tf


def ingest_file(
    csv_path: pathlib.Path, out_root: pathlib.Path, default_tf: str = "1h"
) -> str:
    symbol, tf = infer_symbol_and_tf(csv_path, default_tf)
    # Load
    df = pd.read_csv(csv_path, parse_dates=["Date"])
    df = _normalize(df, symbol)
    # Resample if needed
    df = _resample(df, tf)
    # Save to Parquet
    out_dir = out_root / f"prices_{tf}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{symbol}.parquet"
    _save_parquet(df, str(out_path))
    return str(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src", required=True, help="Root folder with CSVs (recursively scanned)"
    )
    ap.add_argument(
        "--out", default="data", help="Output root (will create prices_<tf>/)"
    )
    ap.add_argument("--default-tf", default="1h", choices=["1m", "5m", "1h", "1d"])
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    out_root = pathlib.Path(args.out)
    files = [p for p in src.rglob("*.csv")]
    if not files:
        print(f"No CSV files under {src}")
        return 0
    print(f"Found {len(files)} CSV files. Ingesting...")
    written = []
    for i, f in enumerate(sorted(files), 1):
        try:
            outp = ingest_file(f, out_root, args.default_tf)
            written.append(outp)
            if i % 20 == 0:
                print(f"... {i} files processed")
        except Exception as e:
            print(f"[WARN] Failed {f}: {e}")
    print(f"Done. Wrote {len(written)} Parquet files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
