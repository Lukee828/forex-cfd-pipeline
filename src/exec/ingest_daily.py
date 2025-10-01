# src/exec/ingest_daily.py
import argparse
from pathlib import Path
import pandas as pd
from src.data.sqlite_store import OHLCVStore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv_folder", default="data/prices_1d")
    ap.add_argument("--db", default="db/market.sqlite")
    ap.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US500"],
    )
    args = ap.parse_args()

    st = OHLCVStore(args.db)
    for s in args.symbols:
        fp = Path(args.csv_folder) / f"{s}.csv"
        df = pd.read_csv(fp, parse_dates=["ts"]).set_index("ts").sort_index()
        st.upsert_frame(s, df)
    print(f"Ingested {len(args.symbols)} symbols into {args.db}")


if __name__ == "__main__":
    main()
