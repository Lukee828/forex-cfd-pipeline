#!/usr/bin/env python
# tools/ma_cross_backtest.py
import argparse
import sys
from pathlib import Path
from datetime import datetime, UTC
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt


def load_closes(symbols, freq):
    base = Path("data") / (f"prices_{freq}")
    # fallback to any other "data/*" if needed
    frames = []
    for sym in symbols:
        pq = base / f"{sym}.parquet"
        if not pq.exists():
            # try to find a parquet anywhere under data
            cands = list(Path("data").rglob(f"{sym}.parquet"))
            if cands:
                pq = cands[0]
        if not pq.exists():
            raise FileNotFoundError(
                f"Parquet for {sym} not found (looked in {base} and under data/**)."
            )
        df = pd.read_parquet(pq)
        # accept common schemas: either wide (has 'Close') or a single column of closes
        if "Close" in df.columns:
            s = df["Close"].rename(sym)
        else:
            # single-column parquet -> treat as closes
            if df.shape[1] != 1:
                raise ValueError(f"{pq} has no 'Close' and is not single-column.")
            s = df.iloc[:, 0].rename(sym)
        s.index = pd.to_datetime(s.index, utc=True, errors="coerce")
        frames.append(s)
    closes = pd.concat(frames, axis=1).sort_index().dropna(how="all")
    return closes


def annualize(series, periods_per_year):
    avg = series.mean() * periods_per_year
    vol = series.std(ddof=0) * np.sqrt(periods_per_year)
    sharpe = (avg / vol) if vol != 0 else 0.0
    return avg, vol, sharpe


def run_ma_cross(closes, fast, slow, start=None, end=None):
    if start or end:
        closes = closes.loc[slice(pd.to_datetime(start), pd.to_datetime(end))]
    rets = (
        closes.pct_change(fill_method=None)
        .replace([np.inf, -np.inf], np.nan)
        .dropna(how="all")
    )
    # Signals per symbol: +1 long if fast>slow, -1 short if fast<slow, 0 otherwise
    fast_ma = closes.rolling(fast, min_periods=fast).mean()
    slow_ma = closes.rolling(slow, min_periods=slow).mean()
    raw_sig = np.where(fast_ma > slow_ma, 1, np.where(fast_ma < slow_ma, -1, 0))
    sig = pd.DataFrame(raw_sig, index=closes.index, columns=closes.columns)
    # Align to returns timing (trade on next bar open/close -> lag signal by 1)
    sig = sig.shift(1).reindex(rets.index)
    # Equal weight across available symbols each day (ignore NaNs gracefully)
    valid = sig.notna()
    counts = valid.sum(axis=1).replace(0, np.nan)
    weights = sig.div(counts, axis=0).fillna(0.0)
    port_rets = (weights * rets).sum(axis=1)
    return port_rets, sig, rets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--symbols",
        default="EURUSD,GBPUSD,USDJPY",
        help='Comma/space list, e.g. "EURUSD,GBPUSD,USDJPY"',
    )
    ap.add_argument("--fast", type=int, default=10)
    ap.add_argument("--slow", type=int, default=50)
    ap.add_argument("--freq", choices=["1d", "1h"], default="1d")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    symbols = [
        s.strip().upper() for s in (args.symbols.replace(",", " ").split()) if s.strip()
    ]
    if args.fast >= args.slow:
        print(
            f"WARNING: fast({args.fast}) >= slow({args.slow}); typical MA cross uses fast<slow.",
            file=sys.stderr,
        )

    closes = load_closes(symbols, args.freq)
    port, sig, rets = run_ma_cross(closes, args.fast, args.slow, args.start, args.end)

    # Metrics
    # Choose periods/year based on freq guess
    periods = 252 if args.freq == "1d" else 252 * 24  # coarse for 1h
    ann_ret, ann_vol, sharpe = annualize(port, periods)
    total = (1 + port).prod() - 1
    start_dt = port.index[0].date() if len(port) else None
    end_dt = port.index[-1].date() if len(port) else None

    print("\n=== MA Cross (vector) ===")
    print(f"Symbols: {symbols}  Fast/Slow: {args.fast}/{args.slow}  Freq: {args.freq}")
    print(f"Rows: {len(port)}  Start: {start_dt}  End: {end_dt}")
    print(
        f"Total: {total*100:0.2f}%  AnnRet: {ann_ret*100:0.2f}%  AnnVol: {ann_vol*100:0.2f}%  Sharpe: {sharpe:0.2f}"
    )

    # Output
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.outdir) if args.outdir else Path("runs") / f"ma_demo_{ts}"
    if args.dry_run:
        print("\n[D R Y   R U N] No files written.")
        return 0

    outdir.mkdir(parents=True, exist_ok=True)
    port.to_frame("ret").to_csv(outdir / "portfolio_returns.csv", index=True)
    closes.to_csv(outdir / "closes.csv")
    (1 + port).cumprod().to_frame("equity").to_csv(outdir / "equity.csv")

    plt.figure()
    (1 + port).cumprod().plot()
    plt.title(f"MA Cross Equity (fast={args.fast}, slow={args.slow}, {args.freq})")
    plt.tight_layout()
    plt.savefig(outdir / "equity.png", dpi=120)
    plt.close()

    print(
        f"\nWrote: {outdir/'equity.png'}, equity.csv, portfolio_returns.csv, closes.csv"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
