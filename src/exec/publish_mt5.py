from __future__ import annotations
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from typing import List, Dict, Any, Optional
import pandas as pd


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Publish orders to MetaTrader 5.

- Reads orders CSV produced by make_orders (columns: symbol, px, lots, target_position, notional_usd).
- Joins with contracts CSV for lot constraints & per-symbol overrides.
- Rounds/normalizes order sizes to lot_step, skips anything < lot_min after rounding, caps at lot_max.
- Chooses fill modes intelligently (IOC for FX/metals, RETURN for indices), but honors CSV fill_mode when set.
- Dry run prints an accurate post-rounding preview table (what would be sent).
"""
# -----------------------------
# Helpers
# -----------------------------


def _step_decimals(step: float) -> int:
    s = f"{step:.10f}".rstrip("0").rstrip(".")
    if "." in s:
        return len(s.split(".")[1])
    return 0


def normalize_volume(vol: float, lot_step: float, lot_min: float, lot_max: float) -> float:
    """
    Round DOWN to step, clamp to [0, lot_max]. Return 0.0 if < lot_min after rounding.
    """
    if vol <= 0.0:
        return 0.0
    decs = _step_decimals(lot_step)
    dvol = Decimal(str(vol))
    dstep = Decimal(str(lot_step))
    units = (dvol / dstep).to_integral_value(rounding=ROUND_FLOOR)
    dv = units * dstep
    dv = min(dv, Decimal(str(lot_max)))
    if dv < Decimal(str(lot_min)):
        return 0.0
    return float(round(dv, decs))


def infer_fill_pref(symbol: str, csv_fill_mode: Optional[int]) -> List[Optional[int]]:
    """
    Return a list of fill modes to try, ordered by likelihood for your broker.
    MT5 constants: RETURN=0, IOC=1, FOK=2. None -> let MT5 decide (often rejected).
    """
    sym = symbol.upper()
    if csv_fill_mode is not None:
        base = [int(csv_fill_mode)]
    else:
        # FX pairs (6 letters) and popular metals: prefer IOC first.
        if sym.startswith("XA") or (len(sym) == 6 and sym[:3].isalpha() and sym[3:].isalpha()):
            base = [1, 0, 2]  # IOC, RETURN, FOK
        else:
            base = [0, 1, 2]  # Indices/CFDs often OK with RETURN
    return base + [None]


def _as_int(x, default=None) -> Optional[int]:
    if pd.isna(x) or (isinstance(x, str) and x.strip() == ""):
        return default
    try:
        return int(float(x))
    except Exception:
        return default


def _as_float(x, default=None) -> Optional[float]:
    if pd.isna(x) or (isinstance(x, str) and x.strip() == ""):
        return default
    try:
        return float(x)
    except Exception:
        return default


# -----------------------------
# Core
# -----------------------------


def load_orders(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"ERR: orders file not found: {path}", file=sys.stderr)
        sys.exit(1)
    orders = pd.read_csv(path)
    need = {"symbol", "px", "lots"}
    if not need.issubset({c.lower() for c in orders.columns} | set(orders.columns)):
        print(
            "ERR: orders.csv must contain columns: symbol,target_position,px,lots",
            file=sys.stderr,
        )
        sys.exit(1)
    # Normalize column names
    cols = {c: c.lower() for c in orders.columns}
    orders = orders.rename(columns=cols)
    return orders[["symbol", "px", "lots"]]


def load_contracts(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(
            f"WARN: contracts file not found: {path}. Proceeding with defaults.",
            file=sys.stderr,
        )
        return pd.DataFrame()
    c = pd.read_csv(path)
    # normalize names
    cols = {cname: cname.lower() for cname in c.columns}
    c = c.rename(columns=cols)
    # expected columns if present
    for col in [
        "symbol",
        "mt5_symbol",
        "lot_min",
        "lot_step",
        "lot_max",
        "deviation",
        "fill_mode",
    ]:
        if col not in c.columns:
            c[col] = pd.NA
    return c


def mt5_init_or_die() -> None:
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    # If no env creds, MT5.initialize() will use the running terminal/session
    if login and password and server:
        ok = mt5.initialize(login=int(login), password=password, server=server)
    else:
        ok = mt5.initialize()
    if not ok:
        print(f"[MT5] initialize failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(3)
    _ = mt5.terminal_info()
    print(
        f"[MT5] initialized (dry_run={False}; login={(login and '(env)') or '(terminal)'} server={(server or '(terminal)')} )"
    )


def build_preview_and_requests(
    orders: pd.DataFrame, contracts: pd.DataFrame, cli_dev: int
) -> tuple[pd.DataFrame, List[Dict[str, Any]]]:
    merged = orders.copy()
    # Join on symbol if contracts present, prefer mt5_symbol when given
    if not contracts.empty:
        merged = merged.merge(contracts, on="symbol", how="left", suffixes=("", "_c"))
        merged["mt5_symbol"] = merged["mt5_symbol"].fillna(merged["symbol"])
    else:
        merged["mt5_symbol"] = merged["symbol"]

    # Numeric cleanup
    for col in ["lot_min", "lot_step", "lot_max"]:
        merged[col] = pd.to_numeric(merged.get(col), errors="coerce")
    merged["deviation"] = pd.to_numeric(merged.get("deviation"), errors="coerce")
    # Defaults
    merged["lot_min"] = merged["lot_min"].fillna(0.01)
    merged["lot_step"] = merged["lot_step"].fillna(0.01)
    merged["lot_max"] = merged["lot_max"].fillna(1e9)
    merged["deviation"] = merged["deviation"].fillna(cli_dev)

    # Side from lots sign, use abs value for normalization
    merged["side"] = merged["lots"].apply(
        lambda x: "SELL" if float(x) < 0 else ("BUY" if float(x) > 0 else "FLAT")
    )
    merged["lots_abs"] = merged["lots"].abs().astype(float)

    # Normalize volumes
    norm_vols = []
    for _, r in merged.iterrows():
        v = normalize_volume(
            vol=float(r["lots_abs"]),
            lot_step=float(r["lot_step"]),
            lot_min=float(r["lot_min"]),
            lot_max=float(r["lot_max"]),
        )
        if r["side"] == "SELL":
            v = -v
        elif r["side"] == "FLAT":
            v = 0.0
        norm_vols.append(v)
    merged["volume"] = norm_vols

    # Build send requests
    to_send: List[Dict[str, Any]] = []
    for _, r in merged.iterrows():
        sym = str(r["mt5_symbol"])
        side = str(r["side"]).upper()
        vol = float(r["volume"])
        if vol == 0.0:
            continue  # skip tiny/flat
        px = float(r["px"])
        # fill prefs
        csv_fill = _as_int(r.get("fill_mode"), None)
        fills = infer_fill_pref(sym, csv_fill)
        req = {
            "symbol": sym,
            "side": side,
            "volume": abs(vol),
            "type": mt5.ORDER_TYPE_SELL if vol < 0 else mt5.ORDER_TYPE_BUY,
            "price": px,
            "deviation": int(r["deviation"]),
            "fills": fills,
        }
        to_send.append(req)

    # Preview table
    preview = merged[
        [
            "symbol",
            "mt5_symbol",
            "side",
            "volume",
            "px",
            "lot_min",
            "lot_step",
            "lot_max",
        ]
    ].rename(columns={"px": "price_used", "symbol": "sym_in"})

    return preview, to_send


def send_orders(requests: List[Dict[str, Any]]) -> Dict[str, str]:
    failed: Dict[str, str] = {}

    for o in requests:
        # Ensure symbol is visible
        si = mt5.symbol_info(o["symbol"])
        if not si or not si.visible:
            mt5.symbol_select(o["symbol"], True)

        tried = []
        sent = False
        for fm in o["fills"]:
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": o["symbol"],
                "volume": o["volume"],
                "type": o["type"],
                "price": o["price"],
                "deviation": o["deviation"],
                "type_time": mt5.ORDER_TIME_GTC,
            }
            if fm is not None:
                req["type_filling"] = fm

            res = mt5.order_send(req)
            tried.append((fm, getattr(res, "retcode", None), getattr(res, "comment", None)))

            if getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:  # 10009
                sent = True
                break

        if not sent:
            print(f"[{o['symbol']}] order failed: {tried}")
            failed[o["symbol"]] = "check contract settings / fill modes"

    return failed


# -----------------------------
# CLI
# -----------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish orders to MT5")
    p.add_argument("--orders_csv", required=True, help="orders.csv path")
    p.add_argument("--contracts_csv", required=True, help="contracts.csv path")
    p.add_argument("--dry_run", default="true", help="true/false (default true)")
    p.add_argument(
        "--deviation",
        type=int,
        default=50,
        help="Default slippage (points) if not set per symbol",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    orders_csv = Path(args.orders_csv)
    contracts_csv = Path(args.contracts_csv)
    dry_run = str(args.dry_run).lower() in {"1", "true", "yes", "y"}

    orders = load_orders(orders_csv)
    contracts = load_contracts(contracts_csv)

    preview, to_send = build_preview_and_requests(orders, contracts, args.deviation)

    # Print preview
    print("MT5 ORDERS (post-rounding preview):")
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(preview.to_string(index=False))

    if dry_run:
        print("MT5 DRY RUN — no orders sent.")
        return

    # Live mode
    mt5_init_or_die()
    failed = send_orders(to_send)

    # Optional: simple reconcile artifact
    try:
        Path("executions").mkdir(parents=True, exist_ok=True)
        run_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        recon_path = Path("executions") / f"reconcile_{run_ts}.csv"
        preview.to_csv(recon_path, index=False)
        print(f"[RECON] saved: {recon_path}")
    except Exception as ex:
        print(f"WARN: failed to write reconcile: {ex}", file=sys.stderr)

    if failed:
        print("Some orders failed:")
        for s, why in failed.items():
            print(f"  {s}: {why}")
        sys.exit(4)

    print("All orders sent.")


if __name__ == "__main__":
    main()
try:
    import MetaTrader5 as mt5  # type: ignore
except Exception as ex:  # pragma: no cover
    import sys

    print(f"ERROR: failed to import MetaTrader5: {ex}", file=sys.stderr)
    mt5 = None
