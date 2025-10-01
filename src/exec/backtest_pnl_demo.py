# src/exec/backtest_pnl_demo.py
"""
Event-driven backtest demo
- Robust OHLCV loader from a folder (CSV or Parquet; flexible filenames/headers)
- Builds signal modules from YAML config (or defaults)
- Runs the engine and writes equity + attribution CSVs

Examples:
  python -m src.exec.backtest_pnl_demo --folder data/prices_1d --out_prefix DEMO
  python -m src.exec.backtest_pnl_demo --folder data/prices_1d --out_prefix DEMO --config config/production.yaml
  python -m src.exec.backtest_pnl_demo --folder data/prices_1d --out_prefix DEMO --symbols EURUSD GBPUSD USDJPY
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import sys
import yaml
import glob
from typing import Dict, List

from src.backtest.engine import (
    MarketData,
    SimBroker,
    Portfolio,
    BacktestEngine,
    OrderEvent,
)

# Signal modules
from src.signals.tf import TrendFollowing
from src.signals.mr import MeanReversion
from src.signals.vol import VolCarry


# ---------------------------
# Robust OHLCV loader
# ---------------------------

_TS_CANDIDATES = ["ts", "timestamp", "datetime", "date_time", "date", "time"]
_OPEN_CANDIDATES = ["open", "o"]
_HIGH_CANDIDATES = ["high", "h"]
_LOW_CANDIDATES = ["low", "l"]
_CLOSE_CANDIDATES = ["close", "c", "adj_close", "adjclose"]
_VOL_CANDIDATES = ["volume", "vol", "qty"]


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    lower_to_orig = {c.lower(): c for c in df.columns}
    for k in candidates:
        if k in lower_to_orig:
            return lower_to_orig[k]
    return None


def _read_frame_normalized(df: pd.DataFrame, source: Path) -> pd.DataFrame:
    """
    Normalize an OHLCV frame so we end up with:
      index: UTC DatetimeIndex
      columns: open, high, low, close, volume
    Works if timestamp is in a column OR already in the index.
    """
    # If timestamp lives in a column
    ts_col = _pick_col(df, _TS_CANDIDATES)

    # If not, check if index looks like datetime (common in Parquet exports)
    if ts_col is None:
        idx = df.index
        # Sometimes the index is already datetime; sometimes it’s str/numeric but convertible
        try:
            ts = pd.to_datetime(idx, errors="coerce", utc=True)
        except Exception:
            ts = pd.Series([pd.NaT] * len(df))
        if ts.notna().any():
            df = df.copy()
            df.insert(0, "__ts__", ts.values)
            ts_col = "__ts__"

    if ts_col is None:
        raise ValueError(
            f"{source}: cannot find a timestamp column or datetime-like index; cols={list(df.columns)}"
        )

    o_col = _pick_col(df, _OPEN_CANDIDATES)
    h_col = _pick_col(df, _HIGH_CANDIDATES)
    l_col = _pick_col(df, _LOW_CANDIDATES)
    c_col = _pick_col(df, _CLOSE_CANDIDATES)
    v_col = _pick_col(df, _VOL_CANDIDATES)

    if not all([o_col, h_col, l_col, c_col]):
        raise ValueError(
            f"{source}: missing one of OHLC columns "
            f"(found: O={o_col}, H={h_col}, L={l_col}, C={c_col})"
        )

    out = pd.DataFrame(
        {
            "ts": pd.to_datetime(df[ts_col], errors="coerce", utc=True),
            "open": pd.to_numeric(df[o_col], errors="coerce"),
            "high": pd.to_numeric(df[h_col], errors="coerce"),
            "low": pd.to_numeric(df[l_col], errors="coerce"),
            "close": pd.to_numeric(df[c_col], errors="coerce"),
        }
    )

    # Volume optional
    if v_col:
        out["volume"] = pd.to_numeric(df[v_col], errors="coerce").fillna(0.0)
    else:
        out["volume"] = 0.0

    # Clean & index
    out = out.dropna(subset=["ts"]).sort_values("ts").set_index("ts")

    # Some exports include a 'symbol' column we don't need
    for col in ("symbol", "Symbol"):
        if col in out.columns:
            out = out.drop(columns=[col])

    return out


def _read_one(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(path)
        return _read_frame_normalized(df, path)
    elif ext == ".parquet":
        try:
            df = pd.read_parquet(path)  # requires pyarrow or fastparquet
        except Exception as e:
            raise RuntimeError(
                f"Failed to read {path} as Parquet. Install a Parquet engine, e.g. `pip install pyarrow`."
            ) from e
        return _read_frame_normalized(df, path)
    else:
        raise ValueError(f"Unsupported file extension for {path}")


def _first_existing(folder: Path, symbol: str) -> Path | None:
    pats = [
        str(folder / f"{symbol}.parquet"),
        str(folder / f"{symbol}_*.parquet"),
        str(folder / f"*{symbol}*.parquet"),
        str(folder / f"{symbol}.csv"),
        str(folder / f"{symbol}_*.csv"),
        str(folder / f"*{symbol}*.csv"),
    ]
    for p in pats:
        hits = sorted(glob.glob(p))
        if hits:
            return Path(hits[0])
    return None


def load_ohlcv(folder: Path, symbols: List[str]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for s in symbols:
        hit = _first_existing(folder, s)
        if not hit:
            raise FileNotFoundError(
                f"Missing price file for {s}. Looked for (parquet/csv): "
                f"{s}.parquet, {s}_*.parquet, *{s}*.parquet, {s}.csv, {s}_*.csv, *{s}*.csv in {folder}"
            )
        df = _read_one(hit)
        out[s] = df[["open", "high", "low", "close", "volume"]]
    return out


# ---------------------------
# Build strategy from config
# ---------------------------


def build_modules_from_config(cfg: dict | None):
    """
    YAML shape:
      signals:
        enable: { TF: true, MR: false, VOL: false }
        params:
          TF:  { lookback: 50, order_size: 0.1 }
          MR:  { z_entry: 1.0, lookback: 20, order_size: 0.05 }
          VOL: { lookback: 30, order_size: 0.05 }
    """
    modules = []

    if not cfg or "signals" not in cfg:
        modules.append(TrendFollowing(lookback=50, order_size=0.1))
        return modules

    sig = cfg.get("signals", {})
    enable = (sig.get("enable") or {}) if isinstance(sig.get("enable"), dict) else {}
    params = (sig.get("params") or {}) if isinstance(sig.get("params"), dict) else {}

    if enable.get("TF", False):
        p = params.get("TF", {})
        modules.append(
            TrendFollowing(
                lookback=int(p.get("lookback", 50)),
                order_size=float(p.get("order_size", 0.1)),
            )
        )

    if enable.get("MR", False):
        p = params.get("MR", {})
        modules.append(
            MeanReversion(
                z_entry=float(p.get("z_entry", 1.0)),
                lookback=int(p.get("lookback", 20)),
                order_size=float(p.get("order_size", 0.05)),
            )
        )

    if enable.get("VOL", False):
        p = params.get("VOL", {})
        modules.append(
            VolCarry(
                lookback=int(p.get("lookback", 30)),
                order_size=float(p.get("order_size", 0.05)),
            )
        )

    if not modules:
        modules.append(TrendFollowing(lookback=50, order_size=0.1))

    return modules


def compose_strategy(modules):
    def _strategy(bar, portfolio):
        all_orders = []
        for m in modules:
            try:
                od = m.on_bar(bar, portfolio)
                if od:
                    for o in od:
                        if not isinstance(o, OrderEvent):
                            raise TypeError(
                                f"{m.__class__.__name__} returned non-OrderEvent"
                            )
                    all_orders.extend(od)
            except Exception as ex:
                print(
                    f"[WARN] {m.__class__.__name__}.on_bar failed: {ex}",
                    file=sys.stderr,
                )
        return all_orders

    return _strategy


# ---------------------------
# CLI
# ---------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--folder", required=True, help="Folder with per-symbol CSV/Parquet files"
    )
    ap.add_argument("--out_prefix", required=True)
    ap.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US500"],
    )
    ap.add_argument(
        "--config",
        default=None,
        help="YAML config with signals enable/params (optional)",
    )
    ap.add_argument("--slippage_bps", type=float, default=1.0)
    ap.add_argument("--spread_bps", type=float, default=0.0)
    ap.add_argument("--commission_per_lot", type=float, default=0.0)
    ap.add_argument("--starting_cash", type=float, default=1_000_000.0)
    args = ap.parse_args()

    folder = Path(args.folder)
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = None
    if args.config:
        with open(args.config, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

    # load data (robust patterns + headers; CSV/Parquet)
    ohlcv = load_ohlcv(folder, args.symbols)

    # build signals
    modules = build_modules_from_config(cfg)
    strategy = compose_strategy(modules)

    # engine parts
    md = MarketData(ohlcv)
    brk = SimBroker(
        slippage_bps=args.slippage_bps,
        spread_bps=args.spread_bps,
        commission_per_lot=args.commission_per_lot,
    )
    pf = Portfolio(starting_cash=args.starting_cash)

    # run
    eng = BacktestEngine(md, brk, pf, strategy)
    eng.run()

    # outputs
    attrib, equity = pf.to_frames()
    eq_path = out_dir / f"{args.out_prefix}_equity.csv"
    at_path = out_dir / f"{args.out_prefix}_attrib_sleeve.csv"
    equity.to_csv(eq_path, index=False)
    attrib.to_csv(at_path, index=False)

    print(f"Saved equity to {eq_path}")
    print(f"Saved attribution to {at_path}")


if __name__ == "__main__":
    main()
