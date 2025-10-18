from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity_csv", default="data/pnl_demo_equity.csv")
    ap.add_argument("--log_csv", default="logs/paper_nav.csv")
    ap.add_argument("--run_id", default=None)
    args = ap.parse_args()

    eq = pd.read_csv(args.equity_csv, parse_dates=["ts"]).set_index("ts")
    if "portfolio_equity" not in eq.columns or eq.empty:
        raise SystemExit("No portfolio_equity in equity CSV.")
    ts = eq.index[-1]
    nav = float(eq["portfolio_equity"].iloc[-1])
    row = pd.DataFrame(
        [
            {
                "ts": ts,
                "nav": nav,
                "run_id": args.run_id or datetime.now().strftime("%Y%m%d_%H%M"),
            }
        ]
    )
    Path(args.log_csv).parent.mkdir(parents=True, exist_ok=True)
    if Path(args.log_csv).exists():
        row.to_csv(args.log_csv, mode="a", header=False, index=False)
    else:
        row.to_csv(args.log_csv, index=False)
    print("Appended to", args.log_csv)


if __name__ == "__main__":
    main()
