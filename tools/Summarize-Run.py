import os
import sys
import glob
import numpy as np
import pandas as pd


def latest_dir(root="runs"):
    runs = [p for p in glob.glob(os.path.join(root, "*")) if os.path.isdir(p)]
    if not runs:
        print("ERROR: no runs/* directories found.")
        sys.exit(2)
    runs.sort(key=os.path.getmtime)
    return runs[-1]


def find_equity_csv(d):
    for name in ("equity.csv", "best_equity.csv", "event_equity.csv"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    for r, _, files in os.walk(d):
        for f in files:
            fl = f.lower()
            if fl.endswith("equity.csv") or "equity" in fl:
                return os.path.join(r, f)
    return None


def load_equity_from_csv(path):
    df = pd.read_csv(path)
    # try to use first col as datetime index
    try:
        idx = pd.to_datetime(df.iloc[:, 0], errors="coerce")
        if idx.notna().sum() >= max(3, len(df) // 5):
            df = df.set_index(df.columns[0])
    except Exception:
        pass
    for c in ["equity", "Equity", "cum_equity", "cumret", "portfolio", "value"]:
        if c in df.columns:
            s = df[c]
            break
    else:
        s = df.select_dtypes(include=[np.number]).iloc[:, -1]
    s = pd.to_numeric(s, errors="coerce").dropna()
    try:
        s.index = pd.to_datetime(s.index, errors="ignore")
    except Exception:
        pass
    return s


def load_equity_from_returns(path):
    df = pd.read_csv(path)
    try:
        idx = pd.to_datetime(df.iloc[:, 0], errors="coerce")
        if idx.notna().sum() >= max(3, len(df) // 5):
            df = df.set_index(df.columns[0])
    except Exception:
        pass
    for c in ["ret", "return", "returns", "portfolio_return", "pnl"]:
        if c in df.columns:
            r = df[c]
            break
    else:
        r = df.select_dtypes(include=[np.number]).iloc[:, -1]
    r = pd.to_numeric(r, errors="coerce").fillna(0.0)
    eq = (1.0 + r).cumprod()
    try:
        eq.index = pd.to_datetime(eq.index, errors="ignore")
    except Exception:
        pass
    return eq


def summarize(eq):
    eq = pd.Series(eq).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if eq.empty:
        return None
    r = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ann = 252.0
    if isinstance(eq.index, pd.DatetimeIndex) and len(eq) > 1:
        dt_years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / dt_years) - 1.0
    else:
        years = max(len(r) / ann, 1e-9)
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0
    vol = r.std() * (ann**0.5) if len(r) else np.nan
    sharpe = (r.mean() * ann) / vol if (vol and vol > 0) else np.nan
    dd = (eq / eq.cummax() - 1.0).min()
    return cagr, vol, sharpe, dd


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--runpath", default="")
    args = ap.parse_args()
    d = args.runpath or latest_dir()
    src = find_equity_csv(d)
    if src:
        eq = load_equity_from_csv(src)
        src_label = os.path.relpath(src)
    else:
        pr = os.path.join(d, "portfolio_returns.csv")
        if not os.path.exists(pr):
            print(f"ERROR: no equity*.csv or portfolio_returns.csv in {d}")
            sys.exit(2)
        eq = load_equity_from_returns(pr)
        src_label = os.path.relpath(pr) + " (reconstructed)"
    stats = summarize(eq)
    if not stats:
        print("ERROR: empty equity series")
        sys.exit(2)
    cagr, vol, sharpe, dd = stats
    print(f"Run: {os.path.relpath(d)}")
    print(f"Source: {src_label}")
    print(f"CAGR: {cagr:.2%}  Vol: {vol:.2%}  Sharpe: {sharpe:.2f}  MaxDD: {dd:.2%}")


if __name__ == "__main__":
    main()
