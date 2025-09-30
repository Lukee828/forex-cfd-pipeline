# src/exec/publish_mt5.py
# ------------------------------------------------------------
# Publish orders to MetaTrader 5 (or just preview with --dry_run true)
# Expects orders.csv created by make_orders.py with at least:
#   symbol,target_position,px,lots
# Uses contracts.csv for MT5 mapping + volume constraints.
# Produces signals/orders_validated.csv preview.
# ------------------------------------------------------------

import argparse
from pathlib import Path
import sys
import math
from datetime import datetime, timezone
import pandas as pd

# Optional dependency: MetaTrader5
try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


def _round_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    return round(x / step) * step


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders_csv", required=True)
    ap.add_argument("--contracts_csv", required=True)
    ap.add_argument("--dry_run", type=lambda x: str(x).lower() == "true", default=True)
    ap.add_argument("--deviation", type=int, default=50, help="default slippage in points")
    ap.add_argument("--margin_buffer_pct", type=float, default=0.0, help="reserve margin buffer %")
    args = ap.parse_args()

    orders_path = Path(args.orders_csv)
    contracts_path = Path(args.contracts_csv)

    if not orders_path.exists():
        print(f"ERR: orders file not found: {orders_path}", file=sys.stderr)
        sys.exit(2)
    if not contracts_path.exists():
        print(f"ERR: contracts file not found: {contracts_path}", file=sys.stderr)
        sys.exit(2)

    # --- Load inputs ---
    orders_df = pd.read_csv(orders_path)
    if not {"symbol", "target_position", "px", "lots"}.issubset(orders_df.columns):
        print("ERR: orders.csv must contain columns: symbol,target_position,px,lots", file=sys.stderr)
        sys.exit(2)

    specs_raw = pd.read_csv(contracts_path)
    if "mt5_symbol" not in specs_raw.columns:
        specs_raw["mt5_symbol"] = specs_raw["symbol"]

    # volume constraints
    for c, dflt in [("lot_min", 0.0), ("lot_max", 1e9), ("lot_step", 0.01)]:
        if c not in specs_raw.columns:
            specs_raw[c] = dflt
        specs_raw[c] = pd.to_numeric(specs_raw[c], errors="coerce").fillna(dflt)

    # user overrides
    if "fill_mode" not in specs_raw.columns:
        specs_raw["fill_mode"] = None
    if "deviation" not in specs_raw.columns:
        specs_raw["deviation"] = None

    specs = specs_raw.set_index("symbol")

    # --- Build validated rows ---
    rows = []
    for _, r in orders_df.iterrows():
        sym_in = str(r["symbol"]).strip()
        if sym_in not in specs.index:
            print(f"WARN: skipping {sym_in} (missing in contracts)", file=sys.stderr)
            continue

        c = specs.loc[sym_in]
        sym_mt5 = str(c.get("mt5_symbol", sym_in)).strip()

        lots_req = _safe_float(r.get("lots", 0.0), 0.0)
        side = "FLAT"
        if lots_req > 0:
            side = "BUY"
        elif lots_req < 0:
            side = "SELL"

        lots_abs = abs(lots_req)
        step = _safe_float(c.get("lot_step", 0.01), 0.01)
        vmin = _safe_float(c.get("lot_min", 0.0), 0.0)
        vmax = _safe_float(c.get("lot_max", 1e9), 1e9)

        lots_rounded = _round_step(lots_abs, step)
        if lots_rounded < max(vmin, step):
            lots_rounded = 0.0
            side = "FLAT"
        lots_rounded = min(lots_rounded, vmax)

        px_used = _safe_float(r.get("px", 0.0), 0.0)

        rows.append(
            dict(
                sym_in=sym_in,
                sym_mt5=sym_mt5,
                side=side,
                volume=(+lots_rounded if side == "BUY" else (-lots_rounded if side == "SELL" else 0.0)),
                price_used=px_used,
                vol_min=vmin,
                vol_step=step,
                vol_max=vmax,
                _fill_pref=c.get("fill_mode", None),
                _deviation=c.get("deviation", None),
            )
        )

    out_df = pd.DataFrame(rows)
    out_validated = orders_path.with_name("orders_validated.csv")
    out_df.to_csv(out_validated, index=False)

    # --- Preview ---
    if len(out_df) == 0:
        print("Nothing to do (no valid orders).")
        return

    print("MT5 ORDERS (post-rounding preview):")
    try:
        print(
            out_df[["sym_in", "sym_mt5", "side", "volume", "price_used", "vol_min", "vol_step", "vol_max"]]
            .to_string(index=False)
        )
    except Exception:
        for rec in rows:
            print(rec)

    if args.dry_run or mt5 is None:
        if mt5 is None and not args.dry_run:
            print("WARN: MetaTrader5 module not available; treated as dry run.")
        print("MT5 DRY RUN — no orders sent.")
        return

    # --- Live send ---
    if not mt5.initialize():
        print("ERR: mt5.initialize() failed.", file=sys.stderr)
        sys.exit(3)

    # sanitize fill/deviation columns
    out_df["_fill_pref"] = pd.to_numeric(out_df["_fill_pref"], errors="coerce")
    out_df["_deviation"] = pd.to_numeric(out_df["_deviation"], errors="coerce")

    failures = []
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for _, rec in out_df.iterrows():
        sym = rec["sym_mt5"]
        side = rec["side"]
        vol = float(rec["volume"])

        if side == "FLAT" or abs(vol) <= 0:
            continue

        si = mt5.symbol_info(sym)
        if si is None:
            if not mt5.symbol_select(sym, True):
                failures.append((sym, "symbol_select_failed"))
                continue
            si = mt5.symbol_info(sym)
        if si is None:
            failures.append((sym, "symbol_info_none"))
            continue

        step = float(si.volume_step) if getattr(si, "volume_step", 0) else float(rec["vol_step"])
        vmin = float(si.volume_min) if getattr(si, "volume_min", 0) else float(rec["vol_min"])
        vmax = float(si.volume_max) if getattr(si, "volume_max", 0) else float(rec["vol_max"])

        vol_adj = _round_step(abs(vol), step)
        if vol_adj < max(vmin, step):
            continue
        vol_adj = min(vol_adj, vmax)

        # deviation
        dev_val = rec.get("_deviation")
        if dev_val is not None and not pd.isna(dev_val):
            try:
                dev_points = int(dev_val)
            except Exception:
                dev_points = int(args.deviation)
        else:
            dev_points = int(args.deviation)

        # build fills
        fm_default = [0, 1, 2]
        fm_pref = []
        si_fill = getattr(si, "filling_mode", None)
        if si_fill in (0, 1, 2):
            fm_pref.append(int(si_fill))
        pref = rec.get("_fill_pref")
        if pref is not None and not pd.isna(pref):
            try:
                pref_i = int(pref)
                if pref_i in (0, 1, 2) and pref_i not in fm_pref:
                    fm_pref.insert(0, pref_i)
            except Exception:
                pass
        for f in fm_default:
            if f not in fm_pref:
                fm_pref.append(f)

        # build base request
        tick = mt5.symbol_info_tick(sym)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": vol_adj,
            "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if side == "BUY" else tick.bid,
            "deviation": dev_points,
            "type_time": mt5.ORDER_TIME_GTC,
        }

        sent = False
        last_ret = None
        for fm in fm_pref:
            req["type_filling"] = fm
            try:
                res = mt5.order_send(req)
                last_ret = res
                if res and getattr(res, "retcode", 0) == mt5.TRADE_RETCODE_DONE:
                    sent = True
                    break
            except Exception as e:
                last_ret = f"exception: {e}"
                continue

        if not sent:
            failures.append((sym, getattr(last_ret, "retcode", last_ret)))

    if failures:
        print("Some orders failed:")
        for sym, rc in failures:
            print(f"  {sym}: retcode={rc}")
        sys.exit(4)


if __name__ == "__main__":
    main()