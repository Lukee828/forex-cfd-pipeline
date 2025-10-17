from __future__ import annotations
import argparse
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--off", action="store_true", help="Disable governor")
    p.add_argument("--vol-target-annual", type=float, default=0.15)
    p.add_argument("--vol-window", type=int, default=30)
    p.add_argument("--vol-min-scale", type=float, default=0.25)
    p.add_argument("--vol-max-scale", type=float, default=2.0)
    p.add_argument("--dd-window", type=int, default=100)
    p.add_argument("--max-dd", type=float, default=0.20)
    p.add_argument("--dd-floor", type=float, default=0.25)
    args = p.parse_args()

    params = GovernorParams(
        enabled=not args.off,
        vol_target_annual=args.vol_target_annual,
        vol_window=args.vol_window,
        vol_min_scale=args.vol_min_scale,
        vol_max_scale=args.vol_max_scale,
        dd_window=args.dd_window,
        max_drawdown=args.max_dd,
        dd_floor_scale=args.dd_floor,
    )
    rg = RiskGovernedSizer(params)

    prices = [100, 101, 99, 98, 100, 104, 102]
    equity = 100_000.0
    for i, px in enumerate(prices):
        if i:
            equity *= 1.0 + (px - prices[i-1]) / prices[i-1]
        scale, info = rg.step(px, equity)
        print(f"{i} price={px:.2f} equity={equity:.2f} scale={scale:.3f} mode={info.get('mode')} dd={info.get('dd_tripped')} vol={info.get('vol_ann')}")

if __name__ == "__main__":
    main()