import argparse
import pandas as pd
import numpy as np
import math


def _drawdown_stats(equity: pd.Series):
    high = -np.inf
    dd_vals = []
    for ts, v in equity.items():
        if v > high:
            high = v
        dd_vals.append(v / high - 1.0)
    dd = pd.Series(dd_vals, index=equity.index)
    max_dd = dd.min()
    end = dd.idxmin()
    start = equity.loc[:end].idxmax()
    return max_dd, start, end


def _ann_stats(equity: pd.Series, freq=252):
    ret = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = ret.std() * math.sqrt(freq)
    downside = ret[ret < 0].std() * math.sqrt(freq)
    sharpe = (cagr - 0.0) / vol if vol > 0 else np.nan
    sortino = (cagr - 0.0) / downside if downside > 0 else np.nan
    return cagr, vol, sharpe, sortino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity_csv", default="data/pnl_demo_equity.csv")
    ap.add_argument("--trades_csv", default="data/pnl_demo_trades.csv")
    args = ap.parse_args()

    eq = pd.read_csv(args.equity_csv, parse_dates=["ts"]).set_index("ts")
    port = eq["portfolio_equity"].dropna()
    cagr, vol, sharpe, sortino = _ann_stats(port, freq=252)
    max_dd, dd_start, dd_end = _drawdown_stats(port)

    print("=== Portfolio Metrics ===")
    print(f"CAGR:   {cagr:.2%}")
    print(f"Vol:    {vol:.2%}")
    print(f"Sharpe: {sharpe:.2f}")
    print(f"Sortino:{sortino:.2f}")
    print(f"MaxDD:  {max_dd:.2%} (from {dd_start.date()} to {dd_end.date()})")
    print(
        f"MAR:    { (cagr/abs(max_dd)) if (not np.isnan(cagr) and max_dd<0) else np.nan :.2f}"
    )

    try:
        tr = pd.read_csv(args.trades_csv, parse_dates=["entry_time", "exit_time"])
        n = len(tr)
        wins = (tr["ret_gross"] > 0).sum()
        hit = wins / n if n else np.nan
        avg_win = tr.loc[tr["ret_gross"] > 0, "ret_gross"].mean()
        avg_loss = tr.loc[tr["ret_gross"] <= 0, "ret_gross"].mean()
        print("\n=== Trades ===")
        print(f"Trades: {n}, Hit rate: {hit:.1%}")
        print(f"Avg win: {avg_win:.4f}, Avg loss: {avg_loss:.4f}")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
