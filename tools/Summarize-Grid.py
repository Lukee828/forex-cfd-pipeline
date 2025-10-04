import argparse
import glob
import math
import os
from typing import Optional, Tuple

import numpy as np
import pandas as pd

# --- constants ---
FLOOR_ABS: float = 1e-8  # hard equity floor used during normalization
MIN_EQ_OK: float = 1e-6  # below this, treat equity as invalid for returns / DD
MAX_ABS_LOGR: float = 0.20  # drop bars with |logret| > 0.2 (~22%) as artifact
EPS: float = 1e-12


# ---------- helpers ----------
def infer_periods_per_year(idx: pd.DatetimeIndex) -> float:
    if len(idx) < 2:
        return 252.0
    dt_sec = np.median(np.diff(idx.values).astype("timedelta64[s]").astype(np.int64))
    if dt_sec <= 0:
        return 252.0
    seconds_per_year = 365.25 * 24 * 3600.0
    return max(1.0, float(seconds_per_year) / float(dt_sec))


def detect_and_normalize_equity(csv_path: str) -> pd.Series:
    s = pd.read_csv(csv_path, parse_dates=[0], index_col=0).iloc[:, 0].astype(float)
    s = s.replace([np.inf, -np.inf], np.nan)
    x = s.dropna()
    if len(x) == 0:
        return pd.Series([], dtype=float, name="equity")

    near_one = (np.median(np.abs(x - 1.0)) < 0.2) and (x.min() > 0)
    looks_ret = (x.abs().median() < 0.02) and (x.abs().max() < 0.5)

    # If returns: bound and cumprod to equity
    if looks_ret and not near_one:
        s = (1.0 + s.clip(-0.95, 0.95)).cumprod()

    s = s.ffill().bfill()
    start = float(s.iloc[0]) if len(s) else 1.0
    floor = max(FLOOR_ABS, 1e-6 * start if start > 0 else FLOOR_ABS)
    s = s.clip(lower=floor)
    return s.rename("equity")


def safe_log_returns(e: pd.Series) -> pd.Series:
    e = e.astype(float)
    ok = e > MIN_EQ_OK
    ok2 = ok & ok.shift(1, fill_value=False)
    r = pd.Series(np.nan, index=e.index, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r[ok2] = np.log(e[ok2] / e[ok2].shift(1))
    r = r[np.abs(r) <= MAX_ABS_LOGR]
    return r.dropna()


def masked_max_drawdown(e: pd.Series) -> float:
    v = e.where(e > MIN_EQ_OK)
    if v.dropna().empty:
        return np.nan
    rm = v.cummax()
    dd = (v / rm - 1.0).dropna()
    return float(dd.min()) if len(dd) else np.nan


def load_positions_csv(run_dir: str) -> Optional[pd.DataFrame]:
    """
    Load positions.csv if present. Expect columns = symbols, index = timestamps.
    Returns a DataFrame of int positions, or None if not found.
    """
    p = os.path.join(run_dir, "positions.csv")
    if not os.path.isfile(p):
        return None
    df = pd.read_csv(p, parse_dates=[0], index_col=0)
    # Coerce to numeric ints, missing -> 0
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.fillna(method="ffill").fillna(0.0)
    df = df.astype(int)
    # drop completely empty frames
    if df.shape[1] == 0 or df.abs().sum().sum() == 0:
        return None
    return df.sort_index()


def positions_turnover(positions: pd.DataFrame) -> pd.Series:
    """
    Turnover per bar = 0.5 * sum(|Δposition|) across symbols.
    positions are assumed in [-1, 0, +1] weights per symbol.
    """
    dpos = positions.diff().abs()
    tv = 0.5 * dpos.sum(axis=1)
    tv.name = "turnover"
    return tv


def apply_costs_to_equity(
    equity: pd.Series,
    positions: Optional[pd.DataFrame],
    trading_bps: float,
) -> Tuple[pd.Series, Optional[float]]:
    """
    If positions are provided, subtract per-bar transaction costs from log returns
    and rebuild a *net* equity curve. Return (equity_net, turnover_annualized).
    If positions is None, return (equity, None).
    """
    if positions is None or trading_bps <= 0:
        return equity, None

    # Compute gross log returns from equity
    lr = safe_log_returns(equity)

    # Align positions turnover to the returns index (right-aligned by timestamp)
    tv = positions_turnover(positions)
    # Align: we want costs at the same timestamps as lr. Forward-fill then reindex.
    tv = tv.reindex(lr.index, method="ffill").fillna(0.0)

    # Cost per bar = turnover * (bps / 10_000)
    cost_per_bar = tv * (float(trading_bps) / 10_000.0)

    # Net log returns
    lr_net = lr - cost_per_bar

    # Rebuild net equity with same starting value
    e0 = float(equity.iloc[0])
    eq_net = e0 * np.exp(lr_net.cumsum())
    eq_net = pd.Series(eq_net, index=lr_net.index, name="equity_net")

    # Annualized turnover (simple): mean(turnover) * periods_per_year
    ppy = infer_periods_per_year(lr_net.index)
    turnover_ann = float(tv.mean() * ppy)

    return eq_net, turnover_ann


def stats_from_equity(e: pd.Series) -> dict:
    if len(e) < 3 or e.max() <= 0:
        return dict(
            Total=np.nan,
            CAGR=np.nan,
            Vol=np.nan,
            Sharpe=np.nan,
            Sortino=np.nan,
            Calmar=np.nan,
            MaxDD=np.nan,
            WinRate=np.nan,
            Trades=np.nan,
            Median=np.nan,
            Skew=np.nan,
            Kurtosis=np.nan,
            TurnoverAnn=np.nan,
        )

    lr = safe_log_returns(e)
    ppy = infer_periods_per_year(e.index)
    vol_ann = lr.std(ddof=0) * math.sqrt(ppy) if len(lr) else 0.0
    mu_ann = lr.mean() * ppy if len(lr) else 0.0
    dstd_ann = lr[lr < 0].std(ddof=0) * math.sqrt(ppy) if (lr < 0).any() else np.nan

    sharpe = (mu_ann / vol_ann) if vol_ann and vol_ann > EPS else np.nan
    sortino = (mu_ann / dstd_ann) if dstd_ann and dstd_ann > EPS else np.nan

    e0, eN = float(e.iloc[0]), float(e.iloc[-1])
    total = eN / e0 - 1.0 if e0 > 0 else np.nan
    years = max(1e-9, (e.index[-1] - e.index[0]).days / 365.25)
    cagr = (eN / e0) ** (1 / years) - 1.0 if years > 0 and e0 > 0 else np.nan

    maxdd = masked_max_drawdown(e)
    calmar = (cagr / abs(maxdd)) if (isinstance(maxdd, float) and maxdd < 0) else np.nan

    winrate = float((lr > 0).mean()) if len(lr) else np.nan
    trades = int(lr.shape[0]) if len(lr) else 0
    median = float(lr.median()) if len(lr) else 0.0
    skew = float(lr.skew()) if len(lr) else np.nan
    kurt = float(lr.kurtosis()) if len(lr) else np.nan

    return dict(
        Total=total,
        CAGR=cagr,
        Vol=vol_ann,
        Sharpe=sharpe,
        Sortino=sortino,
        Calmar=calmar,
        MaxDD=maxdd,
        WinRate=winrate,
        Trades=trades,
        Median=median,
        Skew=skew,
        Kurtosis=kurt,
        TurnoverAnn=np.nan,  # filled by caller if positions are used
    )


# ---------- main ----------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--trading-bps", type=float, default=0.0)
    args = ap.parse_args()

    grid = os.path.abspath(args.grid)
    print(f"Summarizing: {grid}")

    rows = []
    for d in sorted(glob.glob(os.path.join(grid, "fast*_slow*"))):
        # prefer equity.csv; fall back to returns.csv
        src = None
        for cand in ("equity.csv", "returns.csv"):
            p = os.path.join(d, cand)
            if os.path.isfile(p):
                src = p
                break
        if src is None:
            continue

        try:
            equity = detect_and_normalize_equity(src)
            # try to load positions for this run
            pos = load_positions_csv(d)
            equity_net, turnover_ann = apply_costs_to_equity(
                equity=equity, positions=pos, trading_bps=args.trading_bps
            )
            stats = stats_from_equity(equity_net)

            # Fill turnover if we computed costs
            if turnover_ann is not None:
                stats["TurnoverAnn"] = turnover_ann

            base = os.path.basename(d)
            fast = int(base.split("_")[0].replace("fast", ""))
            slow = int(base.split("_")[1].replace("slow", ""))

            rows.append(
                dict(
                    fast=fast,
                    slow=slow,
                    Total=stats["Total"],
                    CAGR=stats["CAGR"],
                    Vol=stats["Vol"],
                    Sharpe=stats["Sharpe"],
                    Sortino=stats["Sortino"],
                    Calmar=stats["Calmar"],
                    MaxDD=stats["MaxDD"],
                    WinRate=stats["WinRate"],
                    Trades=stats["Trades"],
                    Median=stats["Median"],
                    Skew=stats["Skew"],
                    Kurtosis=stats["Kurtosis"],
                    TurnoverAnn=stats["TurnoverAnn"],
                    Path=d,
                )
            )
        except Exception as ex:
            print(f"  ! failed on {src}: {ex}")

    if not rows:
        print("No runs found to summarize.")
        return

    df = pd.DataFrame(rows)

    def pct(x: pd.Series) -> pd.Series:
        return (x * 100.0).round(2)

    out = df.copy()
    for col in (
        "Total",
        "CAGR",
        "Vol",
        "Sharpe",
        "Sortino",
        "Calmar",
        "MaxDD",
        "WinRate",
        "Median",
    ):
        if col in out.columns:
            if col in ("Sharpe", "Sortino", "Calmar"):
                out[col] = out[col].round(2)
            else:
                out[col] = pct(out[col]).astype(str) + "%"

    out["Trades"] = out["Trades"].fillna(0).astype(int)
    # TurnoverAnn: show as float with 2 decimals (annualized units)
    if "TurnoverAnn" in out.columns:
        out["TurnoverAnn"] = df["TurnoverAnn"].astype(float).round(2).astype(str)

    out["Skew"] = df["Skew"].round(2)
    out["Kurtosis"] = df["Kurtosis"].round(2)

    out_csv = os.path.join(grid, "summary.csv")
    out.to_csv(out_csv, index=False)

    cols = [
        "fast",
        "slow",
        "Total",
        "CAGR",
        "Vol",
        "Sharpe",
        "Sortino",
        "Calmar",
        "MaxDD",
        "WinRate",
        "Trades",
        "Median",
        "Skew",
        "Kurtosis",
        "Path",
    ]
    print("\nTop 10 (Sharpe):")
    print(
        out.sort_values(["Sharpe", "Sortino", "Calmar"], ascending=False)[cols]
        .head(10)
        .to_string(index=False)
    )
    print(f"\nWrote: {out_csv}")


if __name__ == "__main__":
    main()
