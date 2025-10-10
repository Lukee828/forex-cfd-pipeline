from __future__ import annotations
import argparse
import pandas as pd
from alpha import roc, fwd_return


def main() -> None:
    ap = argparse.ArgumentParser(description="Build simple alpha features from CSV.")
    ap.add_argument(
        "--csv", required=True, help="Input CSV with columns: timestamp, close"
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--roc_n", type=int, default=5)
    ap.add_argument("--horizon", type=int, default=1, help="Forward return horizon")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    # accept either ISO timestamps or plain index
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    if "close" not in df.columns:
        raise RuntimeError("CSV must include 'close' column")

    df["roc"] = roc(df["close"], n=args.roc_n)
    df["label_fwd_ret"] = fwd_return(df["close"], horizon=args.horizon)

    df.to_csv(args.out, index=False)
    print(f"Wrote alpha features: {args.out} (rows={len(df)})")


if __name__ == "__main__":
    main()
