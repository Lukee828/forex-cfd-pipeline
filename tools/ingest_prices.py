from __future__ import annotations
import argparse
from pathlib import Path

from feature.feature_store import FeatureStore

try:
    from datafeed.csv_source import CsvPriceSource
except Exception:
    CsvPriceSource = None


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest prices into FeatureStore")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--csv", help="CSV with columns: timestamp,close")
    ap.add_argument("--db", type=Path, default=Path("runs") / "fs_ingest" / "fs.db")
    ap.add_argument("--version", default=None)
    args = ap.parse_args()

    if args.csv is None:
        raise SystemExit("--csv is required for now")

    if CsvPriceSource is None:
        raise SystemExit("CsvPriceSource not available")

    src = CsvPriceSource(args.csv)
    df = src.fetch(args.symbol)
    print(f"Loaded {len(df)} rows from CSV: {args.csv}")

    store = FeatureStore(args.db)
    store.init()
    n = store.upsert_prices(args.symbol, df)

    from datetime import datetime, timezone

    version = (
        args.version or f"auto-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    )
    pid = store.record_provenance(args.symbol, "prices", f"csv:{args.csv}", version)
    print(f"Upserted {n} rows to FeatureStore; provenance id={pid}")


if __name__ == "__main__":
    main()
