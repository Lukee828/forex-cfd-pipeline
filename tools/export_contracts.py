#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Export contract specs from your MT5 terminal into config/contracts.csv.

It collects per-symbol details (lot_min/step/max, etc.) so the publisher can
round & validate volumes properly.

Usage:
  python tools/export_contracts.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

try:
    import MetaTrader5 as mt5
except Exception as ex:  # pragma: no cover
    print(f"ERROR: failed to import MetaTrader5: {ex}", file=sys.stderr)
    sys.exit(2)


# Choose the symbols you actually trade (safe defaults; extend if needed)
DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "XAUUSD",
    "US500",
]


def safe_symbol_info(symbol: str):
    si = mt5.symbol_info(symbol)
    if not si or not si.visible:
        mt5.symbol_select(symbol, True)
        si = mt5.symbol_info(symbol)
    return si


def main():
    ok = mt5.initialize()
    if not ok:
        print(f"ERROR: MT5 initialize failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(3)

    rows = []
    for sym in DEFAULT_SYMBOLS:
        si = safe_symbol_info(sym)
        if not si:
            print(f"⚠️  Symbol {sym} not found in MT5, skipping")
            continue

        # Guess base/quote (simple heuristics for major FX / common tickers)
        base = ""
        quote = ""
        if len(sym) == 6 and sym[:3].isalpha() and sym[3:].isalpha():
            base, quote = sym[:3], sym[3:]
        elif sym.upper().startswith("XA"):
            base, quote = "XAU", "USD"
        elif sym.upper() == "US500":
            base, quote = "USD", "USD"

        # sane defaults where MT5 doesn't expose contract_size/point_value in a standard way
        contract_size = getattr(si, "trade_contract_size", 0.0) or 1.0
        point_value = getattr(si, "point", 0.0) or 1.0
        pip = 0.0001
        if sym.endswith("JPY"):
            pip = 0.01
        elif sym.upper().startswith("XA"):
            pip = 0.1
        elif sym.upper() == "US500":
            pip = 1.0

        rows.append({
            "symbol": sym,
            "mt5_symbol": sym,
            "contract_size": contract_size,
            "point_value": point_value,
            "pip": pip,
            "base": base,
            "quote": quote,
            "lot_step": getattr(si, "volume_step", 0.01) or 0.01,
            "lot_min": getattr(si, "volume_min", 0.01) or 0.01,
            "lot_max": getattr(si, "volume_max", 100.0) or 100.0,
            # defaults for publisher; can be edited later in CSV
            "px_mult": 1,
            "fill_mode": "",         # leave empty to let code infer IOC/RETURN
            "deviation": "",         # leave empty; CLI default (e.g., 50) will be used
        })

    df = pd.DataFrame(rows)
    out = Path("config") / "contracts.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"✅ Contracts exported to {out}")


if __name__ == "__main__":
    main()