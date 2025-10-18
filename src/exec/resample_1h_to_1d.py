from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def resample_one(src: Path, dst: Path):
    df = pd.read_parquet(src)
    if "Date" in df.columns:
        df = df.set_index(pd.to_datetime(df["Date"], utc=True)).drop(columns=["Date"])
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    ohlc = (
        df[["Open", "High", "Low", "Close"]]
        .resample("1D", label="left", origin="epoch", offset="0H")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    )
    vol = df["Volume"].resample("1D", label="left", origin="epoch", offset="0H").sum(min_count=1)
    out = ohlc.join(vol.rename("Volume")).dropna(how="all").dropna()
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/prices_1h")
    ap.add_argument("--dst", default="data/prices_1d")
    args = ap.parse_args()
    src, dst = Path(args.src), Path(args.dst)
    for p in src.glob("*.parquet"):
        resample_one(p, dst / p.name)
        print("Resampled", p.name)


if __name__ == "__main__":
    main()
