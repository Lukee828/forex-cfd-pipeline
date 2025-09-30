# src/exec/backtest_pnl_demo.py
# Minimal demo backtester (patched: parquet loader, UTC handling, safe prints)

from __future__ import annotations
from pathlib import Path
import argparse
import sys
import os
import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# ----------------------------- helpers -----------------------------

def _to_utc_idx(idx: pd.Index) -> pd.DatetimeIndex:
    """Ensure a UTC DatetimeIndex (handles tz-naive/aware)."""
    di = pd.to_datetime(idx, errors="coerce")
    if getattr(di, "tz", None) is None:
        di = di.tz_localize("UTC")
    else:
        di = di.tz_convert("UTC")
    # ensure sorted & unique
    di = pd.DatetimeIndex(di).sort_values().unique()
    return di

def _read_symbol_file(fp: Path) -> pd.Series:
    """
    Read a single symbol file (.parquet or .csv) and return a UTC-indexed 'close' series.
    Accepts flexible schemas: looks for ts/date/datetime time column and close/px_last/price.
    """
    symbol = fp.stem.upper()

    # Load
    if fp.suffix.lower() == ".parquet":
        df = pd.read_parquet(fp)
    elif fp.suffix.lower() == ".csv":
        df = pd.read_csv(fp)
    else:
        raise ValueError(f"Unsupported extension: {fp}")

    # Normalize columns (case-insensitive)
    cols = {c.lower(): c for c in df.columns}
    # Time column
    time_col = None
    for cand in ("ts", "datetime", "date"):
        if cand in cols:
            time_col = cols[cand]
            break
    # If no explicit time col, try index
    if time_col is not None:
        ts = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col]).copy()
        df.index = ts
    else:
        if isinstance(df.index, pd.DatetimeIndex):
            pass
        else:
            # Last resort: try to_datetime on index
            df.index = pd.to_datetime(df.index, errors="coerce")
    # Price column
    price_col = None
    for cand in ("close", "px_last", "price", "settle", "last"):
        if cand in cols:
            price_col = cols[cand]
            break
    if price_col is None:
        # Sometimes OHLC present
        for cand in ("adj_close", "close_price", "c"):
            if cand in cols:
                price_col = cols[cand]
                break
    if price_col is None:
        # as a fallback: if 'bid' and 'ask' exist, average them
        if "bid" in cols and "ask" in cols:
            df["__close__"] = (pd.to_numeric(df[cols["bid"]], errors="coerce") +
                               pd.to_numeric(df[cols["ask"]], errors="coerce")) / 2.0
            price_col = "__close__"

    if price_col is None:
        # give a clear message
        raise ValueError(
            f"{fp} does not contain a recognizable close/price column. "
            f"Found columns: {list(df.columns)}"
        )

    # Build series
    ser = pd.to_numeric(df[price_col], errors="coerce")
    ser.index = _to_utc_idx(df.index)
    ser = ser.sort_index()
    ser = ser[~ser.index.duplicated(keep="last")]
    ser.name = symbol
    ser = ser.dropna()
    if ser.empty:
        raise ValueError(f"{fp}: close series empty after parsing.")
    return ser

def _load_prices(folder: str | Path) -> pd.DataFrame:
    """
    Load per-symbol Parquet/CSV from a folder into a wide 'close' price panel (columns = symbols).
    """
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"Prices folder not found: {folder}")

    found: List[Path] = []
    found += list(folder.glob("*.parquet"))
    found += list(folder.glob("*.csv"))

    if not found:
        raise FileNotFoundError(f"No price files found in {folder}")

    series_list = []
    errors = []
    for fp in sorted(found):
        try:
            s = _read_symbol_file(fp)
            series_list.append(s)
        except Exception as e:
            errors.append(f"{fp.name}: {e}")

    if not series_list:
        msg = "No usable price data found in {folder}"
        if errors:
            msg += "\nErrors encountered:\n  - " + "\n  - ".join(errors)
        raise FileNotFoundError(msg)

    panel = pd.concat(series_list, axis=1).sort_index()
    # drop columns that are entirely NaN
    panel = panel.dropna(axis=1, how="all")
    # forward fill tiny gaps is OK; but keep it simple here (do nothing).
    if panel.shape[1] == 0:
        raise FileNotFoundError(f"All parsed series were empty in {folder}")
    return panel

# ----------------------------- toy signals & sim (kept simple) -----------------------------

def tsmom_signal(prices: pd.Series, lookbacks=(63, 126, 252)) -> pd.Series:
    """Toy time-series momentum signal: average sign of trailing returns across a few lookbacks."""
    s = pd.Series(0.0, index=prices.index)
    for lb in lookbacks:
        r = prices.pct_change(lb)
        s = s.add(np.sign(r).fillna(0.0), fill_value=0.0)
    s = s / float(len(lookbacks))
    return s.clip(-1.0, 1.0)

def xsec_mom_signals(panel: pd.DataFrame) -> Dict[str, pd.Series]:
    """Cross-sectional momentum ranks (toy): rank each day by trailing 63d return."""
    lb = 63
    rets = panel.pct_change(lb, fill_method=None).copy()
    rets = rets.ffill()  # or .fillna(0.0) if you prefer
    ranks = rets.rank(axis=1, method="average")
    # convert ranks to [-1,1]
    rs = {}
    for s in panel.columns:
        v = ranks[s]
        rs[s] = ((v - v.min()) / (v.max() - v.min()) * 2 - 1).fillna(0.0)
    return rs

def meanrev_signal(prices: pd.Series, lookback=20) -> pd.Series:
    """Toy mean reversion: negative z-score of 10d return within rolling window."""
    r10 = prices.pct_change(10)
    z = (r10 - r10.rolling(lookback).mean()) / (r10.rolling(lookback).std() + 1e-9)
    return (-z).clip(-1.0, 1.0)

def volcarry_signal(prices: pd.Series, lookback=63) -> pd.Series:
    """Toy vol-carry: inverse recent vol as a proxy carry bias (demo only)."""
    vol = prices.pct_change().rolling(lookback).std()
    s = (vol.median() / (vol + 1e-9)) - 1.0
    return s.clip(-1.0, 1.0)

def simulate(
    panel: pd.DataFrame,
    weights: Dict[str, float],
    target_ann_vol: float = 0.1,
    vol_lookback: int = 20,
    max_leverage: float = 2.0,
    mtd_soft: float = -0.06,
    mtd_hard: float = -0.10,
    costs_map: Dict[str, float] | None = None,
    default_cost: float = 0.0005,
    gap_atr_k: float = 3.0,
    atr_map: Dict[str, float] | None = None,
    vol_spike_mult: float = 3.0,
    vol_med: pd.Series | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Toy portfolio simulation using the toy signals above.
    Returns equity DataFrame and trades DataFrame.
    """
    idx = panel.index
    syms = list(panel.columns)

    sigs = {}
    for s in syms:
        px = panel[s].dropna()
        sig = (
            tsmom_signal(px)
            * weights.get("tsmom", 1.0)
            + xsec_mom_signals(panel).get(s, pd.Series(0.0, index=idx)).reindex(idx).fillna(0.0) * weights.get("xsec", 0.8)
            + meanrev_signal(px) * weights.get("mr", 0.6)
            + volcarry_signal(px) * weights.get("volcarry", 0.0)
        )
        sigs[s] = sig.reindex(idx).fillna(0.0).clip(-1.0, 1.0)

    sig_df = pd.DataFrame(sigs, index=idx).fillna(0.0)

    # scale to target vol (very rough)
    px_chg = panel.pct_change(fill_method=None)
    px_chg = px_chg.ffill()  # or .fillna(0.0)
    port_ret = (sig_df.shift(1) * px_chg).sum(axis=1) / max(1, len(syms))
    run_vol = port_ret.rolling(vol_lookback).std().bfill()
    scale = (target_ann_vol / (run_vol * math.sqrt(252))).clip(0, max_leverage)
    w_t = (sig_df.T * scale).T.clip(-max_leverage, max_leverage)

    # naive PnL with costs on turnover
    turnover = w_t.diff().abs().sum(axis=1) / max(1, len(syms))
    costs = turnover * (default_cost if costs_map is None else default_cost)
    px_chg2 = panel.pct_change(fill_method=None).ffill()
    pnl = (w_t.shift(1) * px_chg2).sum(axis=1) / max(1, len(syms)) - costs

    eq = (1 + pnl.fillna(0.0)).cumprod().to_frame("portfolio_equity")
    tr = []
    for d in idx:
        row = w_t.loc[d]
        for s in syms:
            tr.append({"exit_time": d, "symbol": s, "position": row.get(s, 0.0), "pnl": np.nan})
    trades = pd.DataFrame(tr)

    return eq, trades

# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", type=str, default=None, help="(unused in demo)")
    ap.add_argument("--folder", type=str, required=True)
    ap.add_argument("--costs_csv", type=str, default=None)
    ap.add_argument("--cost_perc", type=float, default=0.0005)
    ap.add_argument("--target_ann_vol", type=float, default=0.10)
    ap.add_argument("--vol_lookback", type=int, default=20)
    ap.add_argument("--max_leverage", type=float, default=2.0)
    ap.add_argument("--mtd_soft", type=float, default=-0.06)
    ap.add_argument("--mtd_hard", type=float, default=-0.10)
    ap.add_argument("--w_tsmom", type=float, default=1.0)
    ap.add_argument("--w_xsec", type=float, default=0.8)
    ap.add_argument("--w_mr", type=float, default=0.6)
    ap.add_argument("--w_volcarry", type=float, default=0.0)
    ap.add_argument("--volcarry_top_q", type=float, default=0.35)
    ap.add_argument("--volcarry_bot_q", type=float, default=0.35)
    ap.add_argument("--volcarry_lookback", type=int, default=63)
    ap.add_argument("--gap_atr_k", type=float, default=3.0)
    ap.add_argument("--atr_lookback", type=int, default=14)
    ap.add_argument("--vol_spike_mult", type=float, default=3.0)
    ap.add_argument("--vol_spike_window", type=int, default=60)
    ap.add_argument("--nav", type=float, default=1_000_000)
    ap.add_argument("--start", type=str, default=None)
    ap.add_argument("--end", type=str, default=None)
    ap.add_argument("--out_prefix", type=str, default=None)
    args = ap.parse_args()

    folder = args.folder
    prefix = args.out_prefix

    # Load panel
    panel = _load_prices(folder)

    # Slice by start/end if provided
    if args.start:
        start_ts = pd.Timestamp(args.start, tz="UTC")
        panel = panel.loc[panel.index >= start_ts]
    if args.end:
        end_ts = pd.Timestamp(args.end, tz="UTC")
        panel = panel.loc[panel.index <= end_ts]

    if panel.empty:
        raise ValueError("Panel is empty after slicing. Check start/end vs data coverage.")

    syms = list(panel.columns)
    start_d = panel.index[0].date()
    end_d = panel.index[-1].date()
    print(f"Backtest period: {start_d} -> {end_d} | Symbols: {len(syms)}")

    weights = dict(
        tsmom=args.w_tsmom,
        xsec=args.w_xsec,
        mr=args.w_mr,
        volcarry=args.w_volcarry,
    )

    # Simulate
    eq, trades = simulate(
        panel,
        weights,
        target_ann_vol=args.target_ann_vol,
        vol_lookback=args.vol_lookback,
        max_leverage=args.max_leverage,
        mtd_soft=args.mtd_soft,
        mtd_hard=args.mtd_hard,
        default_cost=args.cost_perc,
        gap_atr_k=args.gap_atr_k,
        vol_spike_mult=args.vol_spike_mult,
    )

    # Metrics
    r = eq["portfolio_equity"].pct_change().fillna(0.0)
    cagr = (eq["portfolio_equity"].iloc[-1]) ** (252.0 / max(1, len(eq))) - 1.0
    vol = r.std() * math.sqrt(252.0)
    sharpe = np.divide(r.mean() * 252.0, r.std() * math.sqrt(252.0) + 1e-12)
    dd = (eq["portfolio_equity"] / eq["portfolio_equity"].cummax() - 1.0).min()
    print(f"Portfolio cum return (after costs): {((eq['portfolio_equity'].iloc[-1]-1)*100):.2f}%")
    print(f"Final equity: {eq['portfolio_equity'].iloc[-1]:.4f}")

    # Outputs
    if prefix:
        eq_out = Path(f"data/{prefix}_equity.csv")
        tr_out = Path(f"data/{prefix}_trades.csv")
        pos_out = Path(f"data/{prefix}_positions.csv")
    else:
        eq_out = Path("data/pnl_demo_equity.csv")
        tr_out = Path("data/pnl_demo_trades.csv")
        pos_out = Path("data/pnl_demo_positions.csv")

    eq_out.parent.mkdir(parents=True, exist_ok=True)
    tr_out.parent.mkdir(parents=True, exist_ok=True)

    eq.reset_index(names="ts").to_csv(eq_out, index=False)
    trades.to_csv(tr_out, index=False)

    # simple end-of-period position snapshot (per symbol last weight)
    snap = trades.sort_values(["symbol", "exit_time"]).groupby("symbol").tail(1)[["symbol", "position"]]
    snap.rename(columns={"position": "target_position"}, inplace=True)
    snap.to_csv(pos_out, index=False)

    print(f"Saved equity to {eq_out}")
    print(f"Saved trades to {tr_out}")
    print(f"Saved positions snapshot to {pos_out}")

    # Attribution placeholder if a consumer expects it and you ran with prefix
    if prefix:
        attrib_path = Path(f"data/{prefix}_attrib_sleeve.csv")
        if not attrib_path.exists():
            pd.DataFrame(columns=["exit_time", "symbol", "sleeve", "pnl"]).to_csv(attrib_path, index=False)

if __name__ == "__main__":
    main()