from __future__ import annotations
import argparse
import os
from src.backtest.data_feed import ParquetDataFeed
from src.backtest.strategies.ma_cross import MACrossStrategy
from src.backtest.engine_loop import EngineLoop


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY,XAUUSD")
    ap.add_argument("--max-steps", type=int, default=1000)
    ap.add_argument("--strategy", default="ma_cross")
    ap.add_argument("--fast", type=int, default=10)
    ap.add_argument("--slow", type=int, default=50)
    ap.add_argument("--parquet", default="data")
    ap.add_argument("--trading-bps", type=float, default=0.0)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    feed = ParquetDataFeed(args.parquet, symbols)

    if args.strategy.lower() != "ma_cross":
        raise ValueError("Only ma_cross is wired in this runner.")

    strat = MACrossStrategy(symbols=symbols, fast=args.fast, slow=args.slow)
    loop = EngineLoop(feed, strat, trading_bps=args.trading_bps)

    out_csv = os.path.join("runs", "equity.csv")
    equity = loop.run(max_steps=args.max_steps, out_csv=out_csv)

    # quick print so PS scripts can grep/see something useful
    total = float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) else 0.0
    print(f"[event-driven] OK — bars={len(equity)} total={total:.2%}. Wrote {out_csv}")


if __name__ == "__main__":
    main()
