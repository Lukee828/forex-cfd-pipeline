from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def make_monthly_table(equity_csv: str) -> pd.DataFrame:
    eq = pd.read_csv(equity_csv, parse_dates=["ts"]).set_index("ts")
    port = eq["portfolio_equity"].dropna()
    r = port.pct_change().fillna(0)
    m = (1 + r).resample("M").prod() - 1
    tb = m.to_frame("Return").reset_index()
    tb["Year"] = tb["ts"].dt.year
    tb["Month"] = tb["ts"].dt.month_name().str[:3]
    pivot = tb.pivot(index="Year", columns="Month", values="Return").sort_index()
    # add YTD
    ytd = (1 + r).groupby([r.index.year]).apply(lambda x: x.add(1).prod() - 1)
    pivot["YTD"] = ytd
    # order months
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    cols = [m for m in months if m in pivot.columns] + (["YTD"] if "YTD" in pivot.columns else [])
    pivot = pivot.reindex(columns=cols)
    return pivot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity_csv", default="data/pnl_demo_equity.csv")
    ap.add_argument("--out_csv", default="reports/monthly_summary.csv")
    args = ap.parse_args()
    df = make_monthly_table(args.equity_csv)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, float_format="%.6f")
    print("Saved monthly summary to", args.out_csv)


if __name__ == "__main__":
    main()
