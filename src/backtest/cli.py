from __future__ import annotations
import argparse, json, os, pandas as pd
from src.data.dukascopy import BarSpec, get_bars
from src.strategies.mr import MeanReversion
from src.strategies.breakout import Breakout
from src.backtest.engine import run_backtest

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="EURUSD")
    p.add_argument("--tf", default="H1")
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2024-01-31")
    p.add_argument("--strategy", choices=["mr","breakout"], default="mr")
    args = p.parse_args()
    spec = BarSpec(args.pair, args.tf, args.start, args.end)
    df = get_bars(spec)
    strat = MeanReversion() if args.strategy=="mr" else Breakout()
    sig = strat.signals(df).signals
    res = run_backtest(df, sig)
    os.makedirs("artifacts", exist_ok=True)
    res["equity_curve"].to_csv("artifacts/equity.csv")
    res["pnl"].to_csv("artifacts/pnl.csv")
    with open("artifacts/summary.json","w") as f: json.dump(res["summary"], f, indent=2)
    print("wrote artifacts/equity.csv, pnl.csv, summary.json")

if __name__=="__main__":
    main()



