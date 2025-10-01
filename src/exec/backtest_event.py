import argparse
from src.backtest.data_feed import ParquetDataFeed
from src.backtest.engine import Engine
from src.backtest.execution import SimulatedBroker
from src.backtest.portfolio import Portfolio
from src.backtest.strategies.ma_cross import MovingAverageCross


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/prices_1d")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD"])
    ap.add_argument("--short", type=int, default=20)
    ap.add_argument("--long", type=int, default=50)
    ap.add_argument("--cash", type=float, default=100_000.0)
    ap.add_argument("--commission", type=float, default=0.0)
    ap.add_argument("--slip_bps", type=float, default=0.0)
    args = ap.parse_args()

    feed = ParquetDataFeed(args.folder, args.symbols)
    strat = MovingAverageCross(short=args.short, long=args.long)
    port = Portfolio(cash=args.cash)
    broker = SimulatedBroker(
        commission_per_trade=args.commission, slip_bps=args.slip_bps
    )
    eng = Engine(feed.stream(), [strat], port, broker)
    eng.run()

    # Simple end-of-run summary
    pos_summary = {
        s: (p.qty, p.avg_px) for s, p in port.positions.items() if abs(p.qty) > 0
    }
    print(
        f"Final equity: {port.equity:,.2f} | Cash: {port.cash:,.2f} | Open positions: {pos_summary}"
    )


if __name__ == "__main__":
    main()
