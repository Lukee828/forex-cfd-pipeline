
import argparse, pandas as pd, numpy as np, yaml, os
from pathlib import Path
from ..core.loader import load_parquet
from ..sleeves.ts_mom import signals as ts_signals_trend
from ..sleeves.xsec_mom_simple import signals_monthly as xsec_monthly
from ..sleeves.mr_ma20_simple import signals_daily as mr_daily

def _load_many(paths):
    dfs = {}
    for p in paths:
        df = load_parquet(p)
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"{p} must have DatetimeIndex")
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        import pathlib
        sym = df['symbol'].dropna().iloc[0] if 'symbol' in df.columns and df['symbol'].notna().any() else pathlib.Path(p).stem.upper()
        df = df[["Open","High","Low","Close","Volume"]].dropna().sort_index()
        df['symbol'] = sym
        dfs[sym] = df
    return dfs

def _mtd_gate_from_equity(equity_csv, soft=-0.06, hard=-0.10):
    # True portfolio equity gate from existing equity file
    eq = pd.read_csv(equity_csv, parse_dates=['ts']).set_index('ts')
    port = eq['portfolio_equity'].dropna()
    if port.empty:
        return 1.0
    last = port.index[-1]
    key = (last.year, last.month)
    month_slice = port[(port.index.year==key[0]) & (port.index.month==key[1])]
    if month_slice.empty:
        return 1.0
    peak = month_slice.cummax().max()
    curr = month_slice.iloc[-1]
    dd = curr/peak - 1.0
    if dd <= hard: return 0.0
    if dd <= soft: return 0.5
    return 1.0

def _mtd_gate_proxy(dfs, soft=-0.06, hard=-0.10):
    # Equal-weight proxy gate if no equity csv available
    panel = pd.concat([dfs[s]['Close'].rename(s) for s in dfs], axis=1).sort_index().ffill()
    idx = (1 + panel.pct_change().mean(axis=1)).cumprod()
    last = idx.index[-1]
    this_month = idx[(idx.index.year==last.year) & (idx.index.month==last.month)]
    peak = this_month.cummax().max()
    curr = this_month.iloc[-1]
    dd = curr/peak - 1.0
    if dd <= hard: return 0.0
    if dd <= soft: return 0.5
    return 1.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--paths", default="")
    ap.add_argument("--folder", default="")
    ap.add_argument("--target_ann_vol", type=float, default=0.12)
    ap.add_argument("--vol_lookback", type=int, default=20)
    ap.add_argument("--max_leverage", type=float, default=3.0)
    ap.add_argument("--w_tsmom", type=float, default=1.0)
    ap.add_argument("--w_xsec", type=float, default=0.8)
    ap.add_argument("--w_mr", type=float, default=0.6)
    ap.add_argument("--mtd_soft", type=float, default=-0.06)
    ap.add_argument("--mtd_hard", type=float, default=-0.10)
    ap.add_argument("--equity_csv", default="data/pnl_demo_equity.csv")
    ap.add_argument("--nav", type=float, default=1_000_000.0)
    ap.add_argument("--out_csv", default=None)
    args = ap.parse_args()

    with open(args.cfg, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    paths = []
    if args.paths:
        paths.extend([p.strip() for p in args.paths.split(",") if p.strip()])
    if args.folder:
        import pathlib
        paths.extend([str(p) for p in pathlib.Path(args.folder).glob("*.parquet")])
    if not paths:
        raise SystemExit("Provide --paths or --folder with daily Parquet files")

    dfs = _load_many(paths)

    # Sleeve signals
    trend = {s: pd.Series(0.0, index=dfs[s].index) for s in dfs.keys()}
    for s in dfs.keys():
        intents = ts_signals_trend(df_d=dfs[s].assign(symbol=s), lookbacks=tuple(cfg["sleeves"]["tsmom"]["lookbacks"]), exit_bars=cfg["sleeves"]["tsmom"]["exit_bars"], symbols=[s])
        for oi in intents:
            if oi.symbol == s:
                trend[s].loc[pd.Timestamp(oi.ts_utc)] = 1.0 if oi.side=="long" else -1.0
        trend[s] = trend[s].replace(0,np.nan).ffill().fillna(0.0)

    xsec = xsec_monthly({s: dfs[s] for s in dfs.keys()})
    mr = {s: mr_daily(dfs[s]) for s in dfs.keys()}

    weights = {"tsmom": args.w_tsmom, "xsec": args.w_xsec, "mr": args.w_mr}

    # As-of date = last common date across symbols
    idx = None
    for s in dfs.keys():
        idx = dfs[s].index if idx is None else idx.intersection(dfs[s].index)
    asof = idx.max()

    # MTD gate: prefer true equity if exists; else proxy
    gate_mult = 1.0
    if args.equity_csv and os.path.exists(args.equity_csv):
        try:
            gate_mult = _mtd_gate_from_equity(args.equity_csv, args.mtd_soft, args.mtd_hard)
        except Exception:
            gate_mult = _mtd_gate_proxy(dfs, args.mtd_soft, args.mtd_hard)
    else:
        gate_mult = _mtd_gate_proxy(dfs, args.mtd_soft, args.mtd_hard)

    rows = []
    for s, df in dfs.items():
        v = (trend[s].loc[asof] * weights["tsmom"] +
             xsec[s].reindex([asof], method='ffill').fillna(0.0).iloc[0] * weights["xsec"] +
             mr[s].reindex([asof], method='ffill').fillna(0.0).iloc[0] * weights["mr"])
        side = int(np.sign(v)) if not np.isnan(v) else 0

        vol = df['Close'].pct_change().rolling(args.vol_lookback, min_periods=max(5, args.vol_lookback//2)).std().iloc[-1] * np.sqrt(252.0)
        if pd.isna(vol) or vol<=0 or side==0:
            lev = 0.0
        else:
            lev = min(args.max_leverage, args.target_ann_vol / float(vol))
            lev *= gate_mult

        rows.append({"date": asof, "symbol": s, "side": side, "leverage": round(float(lev),6), "gross_usd": round(args.nav*float(lev),2)})

    out = args.out_csv or f"out/signals_{asof.date()}.csv"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print("Saved signals to", out)

if __name__ == "__main__":
    main()
