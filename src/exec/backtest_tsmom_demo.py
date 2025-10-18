from __future__ import annotations
import argparse
import yaml
import pandas as pd
from ..core.loader import load_parquet
from ..sleeves.ts_mom import signals as ts_signals
from ..exec.aggregate import to_net


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--tf", default="1d")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--path", required=True, help="Parquet path for symbol/timeframe")
    args = ap.parse_args()

    with open(args.cfg, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    df = load_parquet(args.path)

    # Ensure DatetimeIndex in UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Parquet must have a DatetimeIndex")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Ensure required columns + symbol present
    if "symbol" not in df.columns or df["symbol"].isna().all():
        df = df.copy()
        df["symbol"] = args.symbol

    df = df[["Open", "High", "Low", "Close", "Volume", "symbol"]].dropna().sort_index()

    # Call sleeve directly on the daily DF (DatetimeIndex preserved)
    intents = ts_signals(
        df_d=df,
        lookbacks=tuple(cfg["sleeves"]["tsmom"]["lookbacks"]),
        exit_bars=cfg["sleeves"]["tsmom"]["exit_bars"],
        symbols=[args.symbol],
    )
    net = to_net(intents)
    print(f"Signals generated: {len(intents)}, Net positions after aggregation: {len(net)}")
    for oi in net[:10]:
        print(oi.ts_utc, oi.symbol, oi.side, oi.tag)


if __name__ == "__main__":
    main()
