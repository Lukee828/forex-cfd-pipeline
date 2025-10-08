import argparse
from pathlib import Path

from feature.feature_store import FeatureStore
from datafeed.csv_source import CsvPriceSource


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest prices into FeatureStore (CSV-supported)."
    )
    ap.add_argument("--db", default="runs/fs_ingest/fs.db", help="SQLite DB path")
    ap.add_argument("--symbol", required=True, help="Instrument symbol, e.g., EURUSD")
    ap.add_argument(
        "--csv",
        help="CSV path with at least: timestamp (ISO), close (float). Optional: open, high, low.",
    )
    ap.add_argument(
        "--provenance",
        default=None,
        help="Arbitrary provenance/version label, e.g. v1 or 2024Q4-snapshot",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    store = FeatureStore(db_path)
    store.init()

    if args.csv:
        src = CsvPriceSource(args.csv)
        df = src.fetch(args.symbol)
        print(f"Loaded {len(df)} rows from CSV: {args.csv}")
        n = store.upsert_prices(args.symbol, df)
        prov = args.provenance
        pid = store.record_provenance(
            args.symbol, "prices", f"csv:{args.csv}", prov if prov else None
        )
        print(f"Upserted {n} rows to FeatureStore; provenance id={pid}")
        return

    print("No source specified. Use --csv PATH.")
    return


if __name__ == "__main__":
    main()
