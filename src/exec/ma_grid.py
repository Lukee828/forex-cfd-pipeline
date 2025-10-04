#!/usr/bin/env python
# src/exec/ma_grid.py
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from src.backtest.data_feed import ParquetDataFeed
from src.backtest.engine_loop import EngineLoop
from src.backtest.strategies.ma_cross import MACrossStrategy


def stats_from_equity(eq: pd.Series) -> dict:
    # eq is cumulative equity (1.0 start) or cumulative return curve
    # If eq is prices-like, convert to returns:
    rets = eq.pct_change().fillna(0.0)
    total = float((eq.iloc[-1] / eq.iloc[0]) - 1.0) if len(eq) > 1 else 0.0
    # crude annualization ~252 trading days (adapt if hourly later)
    ann_ret = float(rets.mean() * 252)
    ann_vol = float(rets.std(ddof=0) * np.sqrt(252))
    sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else 0.0
    return {
        "Total": total,
        "AnnRet": ann_ret,
        "AnnVol": ann_vol,
        "Sharpe": sharpe,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY,XAUUSD")
    ap.add_argument("--parquet", default="data")
    ap.add_argument("--fast-min", type=int, default=5)
    ap.add_argument("--fast-max", type=int, default=20)
    ap.add_argument("--slow-min", type=int, default=50)
    ap.add_argument("--slow-max", type=int, default=200)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    feed = ParquetDataFeed(args.parquet, symbols)
    closes = feed.get_closes(limit=args.steps)

    outdir = (
        Path(args.outdir)
        if args.outdir
        else Path("runs") / f"ma_grid_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}"
    )
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    best = {"Sharpe": -1e9, "fast": None, "slow": None, "equity": None}
    for fast in range(args.fast_min, args.fast_max + 1):
        for slow in range(args.slow_min, args.slow_max + 1):
            if fast >= slow:
                continue
            strat = MACrossStrategy(symbols, fast=fast, slow=slow)
            loop = EngineLoop(feed, strat)
            equity = (
                loop.run_from_closes(closes)
                if hasattr(loop, "run_from_closes")
                else loop.run(max_steps=args.steps)
            )
            metrics = stats_from_equity(equity)
            rows.append({"fast": fast, "slow": slow, **metrics})
            if metrics["Sharpe"] > best["Sharpe"]:
                best.update(
                    {
                        "Sharpe": metrics["Sharpe"],
                        "fast": fast,
                        "slow": slow,
                        "equity": equity,
                    }
                )

    df = pd.DataFrame(rows).sort_values(["Sharpe", "Total"], ascending=[False, False])
    df.to_csv(outdir / "ma_grid_results.csv", index=False)

    # Save best equity plot
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure()
        best["equity"].plot(title=f"Best MA (fast={best['fast']}, slow={best['slow']})")
        plt.tight_layout()
        plt.savefig(outdir / "best_equity.png")
        plt.close()
    except Exception as e:
        print(f"[WARN] Could not render plot: {e}")

    print("\n=== MA Grid Summary ===")
    print(f"Symbols: {symbols}")
    print(
        f"Grid size: {(args.fast_max-args.fast_min+1)*(args.slow_max-args.slow_min+1)} combos (fast<slow only)"
    )
    print(f"Top 5 by Sharpe:\n{df.head(5).to_string(index=False)}")
    if best["fast"] is not None:
        print(
            f"\nBest: fast={best['fast']} slow={best['slow']} Sharpe={best['Sharpe']:.2f}"
        )
        # Persist best equity CSV for convenience
        best["equity"].to_frame("equity").to_csv(outdir / "best_equity.csv")
    print(f"\nOutputs in: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
