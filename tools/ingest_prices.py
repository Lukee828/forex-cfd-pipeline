from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from feature.feature_store import FeatureStore

try:
    from datafeed.csv_source import CsvPriceSource  # type: ignore
except Exception:
    CsvPriceSource = None  # type: ignore[assignment]

try:
    from datafeed.yahoo_source import YahooPriceSource  # type: ignore
except Exception:
    YahooPriceSource = None  # type: ignore[assignment]


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest prices into FeatureStore")
    ap.add_argument("--symbol", required=True, help="Instrument symbol, e.g. EURUSD")
    ap.add_argument("--csv", help="Path to CSV for CsvPriceSource")
    ap.add_argument("--yahoo", help="Ticker to fetch via YahooPriceSource")
    ap.add_argument(
        "--db", default=str(Path("runs/fs_ingest/fs.db")), help="SQLite DB path"
    )
    ap.add_argument("--version", default=None, help="Provenance version label")
    args = ap.parse_args()

    store = FeatureStore(args.db)
    store.init()

    # CSV path
    if args.csv and CsvPriceSource:
        src = CsvPriceSource(args.csv)
        df = src.fetch(args.symbol)
        print(f"Loaded {len(df)} rows from CSV: {args.csv}")
        version = (
            args.version
            or f'auto-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}'
        )
        pid = store.record_provenance(args.symbol, "prices", f"csv:{args.csv}", version)
        n = store.upsert_prices(args.symbol, df, provenance_id=pid)
        print(f"Upserted {n} rows to FeatureStore; provenance id={pid}")
        return

    # Yahoo path
    if args.yahoo and YahooPriceSource:
        src = YahooPriceSource()
        df = src.fetch(args.symbol)
        print(f"Fetched {len(df)} rows from Yahoo for {args.symbol}")
        version = (
            args.version
            or f'auto-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}'
        )
        pid = store.record_provenance(
            args.symbol, "prices", f"yahoo:{args.symbol}", version
        )
        n = store.upsert_prices(args.symbol, df, provenance_id=pid)
        print(f"Upserted {n} rows to FeatureStore; provenance id={pid}")
        return

    ap.error("Specify one of --csv or --yahoo")


if __name__ == "__main__":
    main()
