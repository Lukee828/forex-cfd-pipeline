import argparse
import pandas as pd
from feature.feature_store import FeatureStore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument(
        "--csv",
        required=True,
        help="Path to CSV with columns ts,open,high,low,close,volume",
    )
    ap.add_argument("--source", default="csv:manual")
    ap.add_argument("--version", default=None)
    ap.add_argument("--checksum", default=None)
    args = ap.parse_args()

    store = FeatureStore()
    store.init()

    df = pd.read_csv(args.csv)
    if "ts" not in df.columns:
        for alt in ("timestamp", "time", "date", "datetime"):
            if alt in df.columns:
                df = df.rename(columns={alt: "ts"})
                break
    changed = store.upsert_prices(args.symbol, df)
    store.record_provenance(
        args.symbol, "prices", args.source, args.version, args.checksum
    )
    print(f"Upserted {changed} price rows for {args.symbol}")


if __name__ == "__main__":
    main()
