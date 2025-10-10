from __future__ import annotations
import argparse
import pandas as pd
from factors.structure_factors import build_structure_features, StructureConfig


def main() -> None:
    ap = argparse.ArgumentParser(description="Build structure features from price CSV")
    ap.add_argument(
        "--csv", required=True, help="Input CSV with columns: timestamp,close"
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument(
        "--pct", type=float, default=1.0, help="ZigZag % threshold (1.0 = 1%)"
    )
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    # parse timestamp to datetime (assume UTC, tz-naive output)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)

    cfg = StructureConfig(pct=args.pct)
    out = build_structure_features(df, cfg)
    out.to_csv(args.out, index=False)
    print(f"Wrote features: {args.out} (rows={len(out)})")


if __name__ == "__main__":
    main()
