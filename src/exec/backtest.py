# src/exec/backtest.py  (headless-safe)
import argparse
from pathlib import Path
import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, UTC

# Force non-GUI backend before importing pyplot (fixes Tcl/Tk error)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _read_prices_1d(symbol: str) -> pd.DataFrame:
    base = Path("data/prices_1d")
    pq = base / f"{symbol}.parquet"
    csv = base / f"{symbol}.csv"
    if pq.exists():
        df = pd.read_parquet(pq)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        raise FileNotFoundError(
            f"Missing price file for {symbol} in {base} (.parquet or .csv)."
        )

    cols = {c.lower(): c for c in df.columns}
    ts_col = None
    for c in ["timestamp", "time", "date", "datetime"]:
        if c in cols:
            ts_col = cols[c]
            break
    if ts_col:
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        df = df.dropna(subset=[ts_col]).set_index(ts_col).sort_index()
    elif isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        df = df.sort_index()
    else:
        raise ValueError(
            f"{symbol}: cannot find a timestamp column or datetime-like index; cols={list(df.columns)}"
        )

    def pick(*cands):
        for c in cands:
            if c in df.columns:
                return df[c]
            if c.capitalize() in df.columns:
                return df[c.capitalize()]
        return None

    close = pick("close", "bidclose", "askclose", "Close")
    if close is None:
        raise ValueError(
            f"{symbol}: cannot locate Close column; cols={list(df.columns)}"
        )
    out = pd.DataFrame({"Close": pd.to_numeric(close, errors="coerce")}).dropna()
    return out


def _clip(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start:
        start_ts = pd.Timestamp(start, tz="UTC")
        df = df.loc[df.index >= start_ts]
    if end:
        end_ts = pd.Timestamp(end, tz="UTC")
        df = df.loc[df.index <= end_ts]
    return df


def _load_cfg(path: str) -> dict:
    cfgp = Path(path)
    if not cfgp.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    cfg = yaml.safe_load(cfgp.read_text(encoding="utf-8")) or {}
    if "symbols" not in cfg:
        raise KeyError("Config is missing 'symbols' section.")
    core = list(cfg["symbols"].get("core") or [])
    sat = list(cfg["symbols"].get("satellite") or [])
    if not core and not sat:
        raise ValueError(
            "No symbols specified in config.symbols.core or symbols.satellite."
        )
    return {"core": core, "satellite": sat, "raw": cfg}


def _portfolio_returns(close_panel: pd.DataFrame) -> pd.Series:
    # Avoid deprecated default pad fill; keep NaNs as NaNs
    rets = close_panel.pct_change(fill_method=None).dropna(how="all")
    if rets.empty:
        raise ValueError("No returns after pct_change(); check input data range.")
    w = pd.DataFrame(
        np.where(~rets.isna(), 1.0, np.nan), index=rets.index, columns=rets.columns
    )
    w = w.div(w.count(axis=1), axis=0)  # row-wise 1/n for available series
    port = (rets * w).sum(axis=1)
    return port


def _write_outputs(run_dir: Path, rets: pd.Series, close_panel: pd.DataFrame):
    run_dir.mkdir(parents=True, exist_ok=True)
    eq = (1.0 + rets).cumprod()
    close_panel.to_csv(run_dir / "closes.csv")
    rets.to_frame("ret").to_csv(run_dir / "portfolio_returns.csv")
    eq.to_frame("equity").to_csv(run_dir / "equity.csv")

    plt.figure()
    eq.plot()
    plt.title("Equity (Equal-weight Close-to-Close)")
    plt.xlabel("Date (UTC)")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(run_dir / "equity.png", dpi=120)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cfg",
        required=True,
        help="Path to YAML config (requires symbols.core/satellite)",
    )
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    syms = _load_cfg(args.cfg)
    all_syms = [*syms["core"], *syms["satellite"]]
    print(f"Config loaded OK. Core: {syms['core']}  Satellite: {syms['satellite']}")

    frames = {}
    missing = []
    for s in all_syms:
        try:
            df = _clip(_read_prices_1d(s), args.start, args.end)
            if df.empty:
                print(f"WARNING: {s} has no rows in selected date range; skipping.")
                continue
            frames[s] = df["Close"].rename(s)
        except Exception as e:
            print(f"ERROR loading {s}: {e}")
            missing.append(s)

    if not frames:
        print("No symbols loaded; nothing to do.")
        return 2

    closes = pd.concat(frames.values(), axis=1).sort_index()
    if isinstance(closes.index, pd.DatetimeIndex) and closes.index.tz is not None:
        closes = closes.tz_convert("UTC")

    port = _portfolio_returns(closes)

    eq = (1.0 + port).cumprod()
    total_ret = float(eq.iloc[-1] - 1.0)
    ann = float(port.mean() * 252.0)
    vol = float(port.std(ddof=0) * np.sqrt(252.0))
    sharpe = ann / vol if vol > 0 else np.nan

    print("\n=== SUMMARY ===")
    print(f"Rows: {len(eq)}  Start: {eq.index[0].date()}  End: {eq.index[-1].date()}")
    print(
        f"Total: {total_ret:.2%}  AnnRet: {ann:.2%}  AnnVol: {vol:.2%}  Sharpe: {sharpe:.2f}"
    )
    if missing:
        print(f"Missing files for: {missing}")

    if args.dry_run:
        print("\n[D R Y   R U N] No files written.")
        return 0

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / f"backtest_{ts}"
    _write_outputs(run_dir, port, closes)
    print(
        f"\nWrote: {run_dir}/equity.png, equity.csv, portfolio_returns.csv, closes.csv"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
