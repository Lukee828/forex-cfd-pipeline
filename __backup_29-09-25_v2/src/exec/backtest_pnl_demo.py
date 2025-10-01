import argparse
import math
import numpy as np
import pandas as pd
import os
from pathlib import Path

# ---------- Root helpers ----------

PRESET_ROOT = r"C:\Users\speed\Desktop\Forex CFD's system"


def detect_project_root(preset: str = PRESET_ROOT) -> Path:
    env = os.environ.get("PROJECT_ROOT")
    if env and Path(env).exists():
        return Path(env)
    if preset and Path(preset).exists():
        return Path(preset)
    return Path.cwd()


def default_paths():
    ROOT = detect_project_root()
    d1 = ROOT / "data" / "prices_1d"
    dH = ROOT / "data" / "prices_1h"
    folder = d1 if d1.exists() else (dH if dH.exists() else d1)
    cfg = ROOT / "config" / "baseline.yaml"
    costs = ROOT / "data" / "costs_per_symbol.csv"
    return ROOT, folder, cfg, costs


# ---------- IO helpers ----------
def _read_price_file(p: Path) -> pd.DataFrame:
    df = pd.read_parquet(p)
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df = df.set_index(pd.to_datetime(df["Date"], utc=True, errors="coerce"))
        else:
            raise ValueError(f"{p} must have DatetimeIndex or a Date column")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df = df.sort_index()
    need = ["Open", "High", "Low", "Close"]
    for c in need:
        if c not in df.columns:
            raise ValueError(f"{p} missing column: {c}")
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _load_folder(folder: Path) -> dict:
    out = {}
    for p in sorted(folder.glob("*.parquet")):
        sym = p.stem.upper()
        out[sym] = _read_price_file(p)
    if not out:
        raise SystemExit(f"No Parquet files under {folder}")
    return out


def _load_costs_map(path_csv: Path, fallback=0.0005) -> dict:
    m = {}
    if path_csv and path_csv.exists():
        tb = pd.read_csv(path_csv)
        tb.columns = [c.strip().lower() for c in tb.columns]
        symcol = "symbol" if "symbol" in tb.columns else None
        if symcol:
            for _, r in tb.iterrows():
                s = str(r["symbol"]).upper()
                if {
                    "entry_half_spread_bps",
                    "exit_half_spread_bps",
                    "entry_commission_per_million",
                    "exit_commission_per_million",
                }.issubset(tb.columns):
                    e = (float(r.get("entry_half_spread_bps", 0)) / 10000.0) + (
                        float(r.get("entry_commission_per_million", 0)) / 1_000_000.0
                    )
                    x = (float(r.get("exit_half_spread_bps", 0)) / 10000.0) + (
                        float(r.get("exit_commission_per_million", 0)) / 1_000_000.0
                    )
                    m[s] = (e if e > 0 else fallback, x if x > 0 else fallback)
                elif "cost_perc" in tb.columns:
                    c = float(r["cost_perc"])
                    m[s] = (c if c > 0 else fallback, c if c > 0 else fallback)
    return m


# ---------- Sleeves (self-contained) ----------
def tsmom_signal(df: pd.DataFrame, lookbacks=(63, 126, 252)) -> pd.Series:
    c = df["Close"]
    sigs = []
    for lb in lookbacks:
        s = np.sign(c / c.shift(lb) - 1.0)
        sigs.append(s)
    v = pd.concat(sigs, axis=1).mean(axis=1)
    return v


def xsec_mom_signals(panel: dict, lookbacks=(63, 126, 252)) -> dict:
    """
    Cross-sectional momentum (tz-safe & monotonic):
      - compute multi-horizon momentum score per symbol
      - rebalance each month at the last available trading timestamp <= month-end
      - long top quartile, short bottom quartile
    """
    import pandas as pd

    # unified tz-aware calendar
    idx_all = None
    for s, df in panel.items():
        idx_all = df.index if idx_all is None else idx_all.union(df.index)
    idx_all = idx_all.sort_values()
    if idx_all.tz is None:
        idx_all = idx_all.tz_localize("UTC")
    else:
        idx_all = idx_all.tz_convert("UTC")

    # multi-horizon scores per symbol (on each symbol's index, combined on idx_all)
    scores = {}
    for s, df in panel.items():
        c = df["Close"]
        parts = [c.pct_change(lb) for lb in lookbacks]
        sc = pd.concat(parts, axis=1).mean(axis=1)
        # align to idx_all for clean slicing later
        sc = sc.reindex(idx_all).ffill()
        scores[s] = sc
    scores_df = pd.DataFrame(scores, index=idx_all)

    # calendar month-ends (tz-naive) -> make tz-aware, then snap to trading index
    cal_me = (
        idx_all.tz_convert("UTC")
        .tz_localize(None)
        .to_period("M")
        .to_timestamp("M")
        .tz_localize("UTC")
    )

    cal_me = cal_me.unique().sort_values()

    # helper: snap calendar date to last trading ts <= date
    # returns None if there is no earlier ts (e.g., at the very start)
    def snap_left(ts):
        # position of the right insertion point minus 1
        pos = idx_all.searchsorted(ts, side="right") - 1
        return idx_all[pos] if pos >= 0 else None

    # collect sparse events, then build monotonic series per symbol
    events = {s: [] for s in panel.keys()}

    for d in cal_me:
        upto = scores_df.loc[:d]
        if len(upto) == 0:
            continue
        row = upto.iloc[-1]
        if row.isna().all():
            continue

        ranks = row.rank(method="first", na_option="keep")
        n = ranks.count()
        if n < 4:
            continue
        top_cut = ranks.quantile(0.75)
        bot_cut = ranks.quantile(0.25)
        longs = ranks[ranks >= top_cut].index
        shorts = ranks[ranks <= bot_cut].index

        ts_eff = snap_left(d)
        if ts_eff is None:
            continue
        for s in longs:
            events[s].append((ts_eff, 1.0))
        for s in shorts:
            events[s].append((ts_eff, -1.0))

    out = {}
    for s in panel.keys():
        if events[s]:
            ts_list, val_list = zip(*events[s])
            ser = pd.Series(
                val_list, index=pd.DatetimeIndex(ts_list, tz="UTC")
            ).sort_index()
            # if multiple events land on same ts, keep the last
            ser = ser.groupby(ser.index).last()
        else:
            ser = pd.Series(dtype=float)
        # reindex on the master calendar, forward-fill, fill holes with 0
        ser = ser.reindex(idx_all).ffill().fillna(0.0)
        out[s] = ser

    return out


def meanrev_signal(df: pd.DataFrame, ma=20) -> pd.Series:
    c = df["Close"]
    mu = c.rolling(ma, min_periods=max(5, ma // 2)).mean()
    sd = c.pct_change().rolling(ma, min_periods=max(5, ma // 2)).std()
    z = (c - mu) / (sd * mu + 1e-12)
    return -np.tanh(z)  # scale to [-1,1] and invert (mean reversion)


def volcarry_xsec_signals(panel: dict, lookback=63, top_q=0.35, bot_q=0.35) -> dict:
    # lower vol -> long, higher vol -> short (carry proxy)
    idx_all = None
    for s, df in panel.items():
        idx_all = df.index if idx_all is None else idx_all.union(df.index)
    idx_all = idx_all.sort_values()
    vols = {
        s: df["Close"]
        .pct_change()
        .rolling(lookback, min_periods=max(5, lookback // 2))
        .std()
        for s, df in panel.items()
    }
    V = pd.DataFrame(vols).reindex(idx_all).ffill()
    out = {s: pd.Series(0.0, index=idx_all) for s in panel.keys()}
    for d, row in V.iterrows():
        if row.isna().all():
            continue
        ranks = row.rank(ascending=True)  # small vol = rank 1
        n = ranks.count()
        if n < 4:
            continue
        top_cut = ranks.quantile(top_q)  # long small vol (low rank)
        bot_cut = ranks.quantile(1.0 - bot_q)  # short big vol (high rank)
        longs = ranks[ranks <= top_cut].index
        shorts = ranks[ranks >= bot_cut].index
        for s in longs:
            out[s].loc[d] = 1.0
        for s in shorts:
            out[s].loc[d] = -1.0
    for s in out:
        out[s] = out[s].replace(0, np.nan).ffill().fillna(0.0)
    return out


# ---------- Risk / sim ----------
def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    c = df["Close"]
    tr1 = (df["High"] - df["Low"]).abs()
    tr2 = (df["High"] - c.shift()).abs()
    tr3 = (df["Low"] - c.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=max(5, n // 2)).mean()


def simulate(
    panel: dict,
    weights: dict,
    target_ann_vol=0.12,
    vol_lookback=20,
    max_leverage=3.0,
    mtd_soft=-0.06,
    mtd_hard=-0.10,
    costs_map=None,
    default_cost=0.0005,
    gap_atr_k=3.0,
    atr_map=None,
    vol_spike_mult=3.0,
    vol_med=None,
):
    symbols = sorted(panel.keys())
    # build unified calendar
    cal = None
    for s in symbols:
        idx = panel[s].index
        cal = idx if cal is None else cal.intersection(idx)
    cal = cal.sort_values()
    # vol estimates
    vol_est = {
        s: panel[s]["Close"]
        .pct_change()
        .rolling(vol_lookback, min_periods=max(5, vol_lookback // 2))
        .std()
        * math.sqrt(252.0)
        for s in symbols
    }
    leg_cost = {
        s: (
            costs_map.get(s, (default_cost, default_cost))
            if costs_map
            else (default_cost, default_cost)
        )
        for s in symbols
    }
    # signals
    tsm = {s: tsmom_signal(panel[s]) for s in symbols}
    xsm = xsec_mom_signals(panel)
    mrv = {s: meanrev_signal(panel[s]) for s in symbols}
    vcr = volcarry_xsec_signals(
        panel, lookback=max(20, int(vol_lookback * 3)), top_q=0.35, bot_q=0.35
    )

    # combine
    comb = {}
    for s in symbols:
        idx = panel[s].index
        v = (
            tsm[s].reindex(idx, method="ffill").fillna(0.0) * weights.get("tsmom", 1.0)
            + xsm[s].reindex(idx, method="ffill").fillna(0.0) * weights.get("xsec", 0.8)
            + mrv[s].reindex(idx, method="ffill").fillna(0.0) * weights.get("mr", 0.6)
            + vcr[s].reindex(idx, method="ffill").fillna(0.0)
            * weights.get("volcarry", 0.4)
        )
        comb[s] = np.sign(v).replace(0, 0.0)

    pos = {s: 0 for s in symbols}
    entry = {s: None for s in symbols}
    eq = {s: 1.0 for s in symbols}
    rows_eq = []
    rows_tr = []
    port_eq = 1.0
    mtd_peak = 1.0
    current_m = None

    for i, d in enumerate(cal[:-1]):
        nd = cal[i + 1]
        mkey = (d.year, d.month)
        if mkey != current_m:
            current_m = mkey
            mtd_peak = port_eq
        mtd_peak = max(mtd_peak, port_eq)
        mtd_dd = port_eq / mtd_peak - 1.0
        gate = 0.0 if mtd_dd <= mtd_hard else (0.5 if mtd_dd <= mtd_soft else 1.0)

        for s in symbols:
            df = panel[s]
            if d not in df.index or nd not in df.index:
                continue
            open_next = float(df.loc[nd, "Open"])
            signal = float(comb[s].get(d, 0.0))

            # exits
            if pos[s] != 0:
                # flip or zero signal -> exit
                if signal * pos[s] <= 0:
                    e_d, e_px, e_side, lev = entry[s]
                    ret = (open_next / e_px - 1.0) * e_side
                    eq[s] *= 1.0 + lev * ret
                    eq[s] -= eq[s] * leg_cost[s][1]
                    rows_tr.append(
                        dict(
                            symbol=s,
                            entry_time=e_d,
                            exit_time=nd,
                            side=("long" if e_side > 0 else "short"),
                            entry_px=e_px,
                            exit_px=open_next,
                            leverage=lev,
                            ret_gross=ret * lev,
                        )
                    )
                    pos[s] = 0
                    entry[s] = None

            # entries (or re-entries after exit)
            if pos[s] == 0 and signal != 0 and gate > 0.0:
                volh = float(vol_est[s].get(d, np.nan))
                lev = (
                    min(
                        max_leverage,
                        (
                            target_ann_vol / volh
                            if (not np.isnan(volh) and volh > 0)
                            else 0.0
                        ),
                    )
                    * gate
                )
                # sanity guards
                if lev > 0.0 and atr_map and s in atr_map:
                    prev_close = float(df.loc[d, "Close"])
                    atr_prev = float(atr_map[s].get(d, np.nan))
                    if (
                        not np.isnan(atr_prev)
                        and atr_prev > 0
                        and abs(open_next - prev_close) > gap_atr_k * atr_prev
                    ):
                        lev = 0.0
                if lev > 0.0 and vol_med and s in vol_med:
                    vm = float(vol_med[s].get(d, np.nan))
                    if (
                        not np.isnan(vm)
                        and vm > 0
                        and not np.isnan(volh)
                        and volh > vol_spike_mult * vm
                    ):
                        lev = 0.0
                if lev > 0.0:
                    pos[s] = int(np.sign(signal))
                    entry[s] = (nd, open_next, pos[s], lev)
                    eq[s] -= eq[s] * leg_cost[s][0]

        # mark to market equity at next d
        for s in symbols:
            rows_eq.append((nd, s, eq[s]))
        port_eq = float(np.mean(list(eq.values())))

    eq_df = pd.DataFrame(rows_eq, columns=["ts", "symbol", "equity"]).set_index("ts")
    merged = None
    for s in symbols:
        sub = eq_df[eq_df["symbol"] == s][["equity"]].rename(
            columns={"equity": f"equity_{s}"}
        )
        merged = sub if merged is None else merged.join(sub, how="outer")
    merged = merged.sort_index().ffill().fillna(1.0)
    merged["portfolio_equity"] = merged.filter(like="equity_").mean(axis=1)

    trades = pd.DataFrame(rows_tr)
    return merged, trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--folder", default=None)
    ap.add_argument("--costs_csv", default=None)
    ap.add_argument("--cost_perc", type=float, default=0.0005)
    ap.add_argument("--target_ann_vol", type=float, default=0.12)
    ap.add_argument("--vol_lookback", type=int, default=20)
    ap.add_argument("--max_leverage", type=float, default=3.0)
    ap.add_argument("--mtd_soft", type=float, default=-0.06)
    ap.add_argument("--mtd_hard", type=float, default=-0.10)
    ap.add_argument("--w_tsmom", type=float, default=1.0)
    ap.add_argument("--w_xsec", type=float, default=0.8)
    ap.add_argument("--w_mr", type=float, default=0.6)
    ap.add_argument("--w_volcarry", type=float, default=0.4)
    ap.add_argument(
        "--volcarry_top_q", type=float, default=0.35
    )  # (kept for CLI compatibility, used inside sim default)
    ap.add_argument("--volcarry_bot_q", type=float, default=0.35)
    ap.add_argument("--volcarry_lookback", type=int, default=63)
    ap.add_argument("--gap_atr_k", type=float, default=3.0)
    ap.add_argument("--atr_lookback", type=int, default=14)
    ap.add_argument("--vol_spike_mult", type=float, default=3.0)
    ap.add_argument("--vol_spike_window", type=int, default=60)
    ap.add_argument("--nav", type=float, default=1_000_000.0)
    args = ap.parse_args()

    ROOT, DEF_FOLDER, DEF_CFG, DEF_COSTS = default_paths()
    folder = Path(args.folder) if args.folder else DEF_FOLDER
    costs_csv = Path(args.costs_csv) if args.costs_csv else DEF_COSTS
    if not folder.exists():
        raise SystemExit(f"Data folder not found: {folder}")

    panel = _load_folder(folder)
    costs_map = _load_costs_map(costs_csv, fallback=args.cost_perc)
    atr_map = {s: _atr(df, args.atr_lookback) for s, df in panel.items()}
    vol_med = {
        s: df["Close"]
        .pct_change()
        .rolling(args.vol_spike_window, min_periods=max(5, args.vol_spike_window // 2))
        .std()
        * math.sqrt(252.0)
        for s, df in panel.items()
    }

    weights = dict(
        tsmom=args.w_tsmom, xsec=args.w_xsec, mr=args.w_mr, volcarry=args.w_volcarry
    )
    eq, trades = simulate(
        panel,
        weights,
        target_ann_vol=args.target_ann_vol,
        vol_lookback=args.vol_lookback,
        max_leverage=args.max_leverage,
        mtd_soft=args.mtd_soft,
        mtd_hard=args.mtd_hard,
        costs_map=costs_map,
        default_cost=args.cost_perc,
        gap_atr_k=args.gap_atr_k,
        atr_map=atr_map,
        vol_spike_mult=args.vol_spike_mult,
        vol_med=vol_med,
    )

    Path("data").mkdir(exist_ok=True)
    eq.to_csv("data/pnl_demo_equity.csv")
    if len(trades):
        trades.to_csv("data/pnl_demo_trades.csv", index=False)

    # attribution proxy by sleeves weights at exit is omitted here for simplicity; keep interface compatible:
    Path("data").mkdir(exist_ok=True)
    # (optional) create empty file if not present
    if not (Path("data") / "pnl_demo_attrib_sleeve.csv").exists():
        pd.DataFrame(columns=["exit_time", "symbol", "sleeve", "pnl"]).to_csv(
            "data/pnl_demo_attrib_sleeve.csv", index=False
        )

    start, end = eq.index.min(), eq.index.max()
    cumret = float(eq["portfolio_equity"].iloc[-1] - 1.0)
    nsyms = len([c for c in eq.columns if c.startswith("equity_")])
    print(f"Backtest period: {start.date()} -> {end.date()} | Symbols: {nsyms}")
    print(f"Portfolio cum return (after costs): {cumret:.2%}")
    print(f"Final equity: {eq['portfolio_equity'].iloc[-1]:.4f}")
    print("Saved equity to data/pnl_demo_equity.csv")
    if len(trades):
        print("Saved trades to data/pnl_demo_trades.csv")


if __name__ == "__main__":
    main()
