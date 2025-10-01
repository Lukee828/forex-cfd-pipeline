#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Build orders.csv from a positions snapshot + latest prices.

Input:
  - positions_csv: CSV with at least: symbol, target_position
      * target_position is the *fraction of NAV* (can be negative).
  - contracts_csv: (optional but recommended) instrument metadata
      columns used (when present): symbol, px_mult, contract_size
      fallback defaults:
        px_mult = 1
        contract_size = 100_000 for FX (6-letter pairs), else 1
  - prices_folder: folder with daily price CSVs named <symbol>.csv
      each file should have a 'close' (or 'px') column; last row used
  - nav: account NAV in USD
  - gross_cap: informational only (we do NOT rescale positions here).
  - max_price_age_days: warn if price is stale
  - max_dev_bps: allow a “sanity” warning vs live MT5 ticks if available

Output:
  signals/orders.csv with columns:
    symbol,target_position,px,notional_usd,lots

Notes:
  - lots are computed as: notional_usd / (contract_size * px)
    (so for EURUSD, 1 lot = 100k base; we divide by contract_size then price)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

# Optional MT5 price sanity (if terminal is running)
try:
    import MetaTrader5 as mt5  # type: ignore

    _HAVE_MT5 = True
except Exception:
    _HAVE_MT5 = False


def _read_positions(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"ERR: positions file not found: {path}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(path)
    # normalize headers
    df.columns = [c.lower() for c in df.columns]
    need = {"symbol", "target_position"}
    if not need.issubset(set(df.columns)):
        print(
            "ERR: positions.csv must contain at least: symbol,target_position",
            file=sys.stderr,
        )
        sys.exit(1)
    # keep only relevant cols
    return df[["symbol", "target_position"]]


def _read_contracts(path: Optional[Path]) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame(columns=["symbol", "px_mult", "contract_size"])
    c = pd.read_csv(path)
    c.columns = [x.lower() for x in c.columns]
    # ensure required hints exist
    if "px_mult" not in c.columns:
        c["px_mult"] = 1.0
    if "contract_size" not in c.columns:
        c["contract_size"] = pd.NA
    return c[["symbol", "px_mult", "contract_size"]]


def _infer_contract_size(symbol: str, contract_row: Optional[pd.Series]) -> float:
    if contract_row is not None and pd.notna(contract_row.get("contract_size", pd.NA)):
        try:
            return float(contract_row["contract_size"])
        except Exception:
            pass
    # heuristic defaults
    sym = symbol.upper()
    if len(sym) == 6 and sym[:3].isalpha() and sym[3:].isalpha():
        return 100_000.0  # FX 1 lot = 100k base
    if sym.startswith("XA"):  # XAUUSD, XAGUSD etc.
        return 100.0
    return 1.0


def _load_last_price(
    prices_folder: Path, symbol: str
) -> tuple[float, Optional[datetime]]:
    f = prices_folder / f"{symbol}.csv"
    if not f.exists():
        print(f"ERR: price file missing for {symbol}: {f}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(f)
    df.columns = [c.lower() for c in df.columns]
    price_col = (
        "close" if "close" in df.columns else ("px" if "px" in df.columns else None)
    )
    if not price_col:
        print(f"ERR: {f} must contain 'close' or 'px' column", file=sys.stderr)
        sys.exit(1)
    last = df.iloc[-1]
    px = float(last[price_col])
    ts = None
    if "ts" in df.columns:
        try:
            ts = pd.to_datetime(last["ts"], utc=True, errors="coerce").to_pydatetime()
        except Exception:
            ts = None
    return px, ts


def _try_mt5_tick(symbol: str) -> Optional[float]:
    if not _HAVE_MT5:
        return None
    try:
        if not mt5.initialize():
            return None
        si = mt5.symbol_info(symbol)
        if not si or not si.visible:
            mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if tick and getattr(tick, "last", 0.0):
            return float(tick.last)
        if tick and getattr(tick, "ask", 0.0):
            return float(tick.ask)
    except Exception:
        return None
    return None


def build_orders(
    positions_csv: Path,
    contracts_csv: Optional[Path],
    prices_folder: Path,
    out_csv: Path,
    nav: float,
    gross_cap: float,
    max_price_age_days: int,
    max_dev_bps: int,
    skip_stale: bool,
) -> pd.DataFrame:

    pos = _read_positions(positions_csv)
    contracts = _read_contracts(contracts_csv)

    # join per-symbol hints
    merged = pos.merge(contracts, on="symbol", how="left", suffixes=("", "_c"))
    merged["px_mult"] = pd.to_numeric(merged["px_mult"], errors="coerce").fillna(1.0)

    rows = []
    now_utc = datetime.now(timezone.utc)
    stale_syms = []

    for _, r in merged.iterrows():
        sym = str(r["symbol"])
        px_raw, ts = _load_last_price(prices_folder, sym)
        if ts is not None:
            age_days = (now_utc - ts).days
            if age_days > max_price_age_days:
                msg = f"{sym} price is stale by {age_days}d (> {max_price_age_days})"
                if skip_stale:
                    print(f"SKIP: {msg}")
                    continue
                else:
                    stale_syms.append(msg)

        px = px_raw * float(r["px_mult"])
        cs = _infer_contract_size(sym, r)
        target = float(r["target_position"])
        notional = target * float(nav)
        lots = 0.0 if px <= 0 or cs <= 0 else (notional / (cs * px))

        rows.append(
            {
                "symbol": sym,
                "target_position": target,
                "px": round(px, 6),
                "notional_usd": notional,
                "lots": lots,
            }
        )

        # optional MT5 sanity
        mt5_px = _try_mt5_tick(sym)
        if mt5_px is not None and px > 0:
            dev_bps = abs((mt5_px / px) - 1.0) * 10_000
            if dev_bps > max_dev_bps:
                print("MT5 price sanity WARN (bps deviation > %.1f):" % max_dev_bps)
                print("symbol dev_bps px_ref_scaled px_mt5")
                print(f"{sym:6s} {dev_bps:8.2f} {px:12.6f} {mt5_px:12.6f}")

    if stale_syms:
        for msg in stale_syms:
            print(f"WARN: {msg}")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_csv, index=False)

    # Gross diagnostics (informational)
    gross_before = float((abs(pos["target_position"]).sum()) * nav)
    scale = 0.0
    if abs(pos["target_position"]).sum() > 0:
        scale = float(gross_cap / abs(pos["target_position"]).sum())
    print(
        f"Saved orders to {out_csv} | gross before scale: {gross_before:,.0f} | scale: {scale:.3f}"
    )

    return out_df


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Create MT5 orders from positions.")
    p.add_argument("--positions_csv", required=True)
    p.add_argument("--contracts_csv", required=False)
    p.add_argument("--prices_folder", required=True)
    p.add_argument("--out_csv", default="signals/orders.csv")
    p.add_argument("--nav", type=float, default=1_000_000.0)
    p.add_argument("--gross_cap", type=float, default=0.20)
    p.add_argument("--max_price_age_days", type=int, default=7)
    p.add_argument("--max_dev_bps", type=int, default=500.0)
    p.add_argument(
        "--skip_stale",
        action="store_true",
        help="skip symbols whose prices are too old",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    build_orders(
        positions_csv=Path(args.positions_csv),
        contracts_csv=Path(args.contracts_csv) if args.contracts_csv else None,
        prices_folder=Path(args.prices_folder),
        out_csv=Path(args.out_csv),
        nav=args.nav,
        gross_cap=args.gross_cap,
        max_price_age_days=args.max_price_age_days,
        max_dev_bps=args.max_dev_bps,
        skip_stale=args.skip_stale,
    )


if __name__ == "__main__":
    main()
