# src/exec/make_orders.py
# ------------------------------------------------------------
# Generate orders.csv from positions.csv + contracts.csv
# Supports Parquet/CSV prices, MT5 symbol mapping, px_mult scaling,
# staleness checks, and MT5 mid-price sanity diff (bps) warnings.
# ------------------------------------------------------------

import argparse
from pathlib import Path
import sys
import re
import pandas as pd


# ---------- time helpers ----------

def _utc_now() -> pd.Timestamp:
    """Return a tz-aware UTC Timestamp safely."""
    ts = pd.Timestamp.utcnow()
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


# ---------- price loading ----------

def _ensure_dt_index(df: pd.DataFrame, src: Path, symbol: str) -> pd.DataFrame:
    """Make the DataFrame indexed by UTC DatetimeIndex."""
    if isinstance(df.index, pd.DatetimeIndex):
        ix = df.index
    else:
        for c in ["Date", "date", "timestamp", "ts"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
                df = df.set_index(c)
                break
        ix = df.index
        if not isinstance(ix, pd.DatetimeIndex):
            raise ValueError(f"{symbol}: could not find datetime index/column in {src}")
    # UTC-ize
    if ix.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df.sort_index()


def load_last_close(folder: Path, symbol: str):
    """
    Load last close & timestamp for a symbol from either Parquet or CSV.

    Accepted schemas:
      - index named 'Date'/'date' or unnamed DatetimeIndex, or columns 'timestamp'/'ts'
      - close column 'Close'/'close'/'c'
    """
    pf = folder / f"{symbol}.parquet"
    cf = folder / f"{symbol}.csv"

    if pf.exists():
        df = pd.read_parquet(pf)
        src = pf
    elif cf.exists():
        # try detect date columns quickly
        first = ""
        try:
            with open(cf, "r", encoding="utf-8", errors="ignore") as fh:
                first = fh.readline()
        except Exception:
            pass
        time_cols = [c for c in ["Date", "date", "timestamp", "ts"] if c in first]
        df = pd.read_csv(cf, parse_dates=time_cols or None)
        src = cf
    else:
        raise FileNotFoundError(f"Price file not found for {symbol}: {cf}")

    df = _ensure_dt_index(df, src, symbol)

    close_col = None
    for c in ["Close", "close", "c"]:
        if c in df.columns:
            close_col = c
            break
    if close_col is None:
        raise ValueError(f"{symbol}: could not find a close column in {src}")

    last_ts = df.index[-1]
    last_px = float(df[close_col].iloc[-1])
    return last_px, last_ts


# ---------- optional MT5 mid ----------

def get_mt5_mid(sym_mt5: str):
    """Try to fetch MT5 mid price, return None if unavailable."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None
        info = mt5.symbol_info_tick(sym_mt5)
        if info is None:
            return None
        bid = getattr(info, "bid", None)
        ask = getattr(info, "ask", None)
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return None
        return (bid + ask) / 2.0
    except Exception:
        return None


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions_csv", required=True)
    ap.add_argument("--contracts_csv", required=True)
    ap.add_argument("--prices_folder", required=True)
    ap.add_argument("--out_csv", default="signals/orders.csv")
    ap.add_argument("--nav", type=float, default=1_000_000.0)
    ap.add_argument("--gross_cap", type=float, default=3.0)
    ap.add_argument("--max_price_age_days", type=int, default=3)
    ap.add_argument("--max_dev_bps", type=float, default=500.0)
    ap.add_argument("--skip_stale", action="store_true", help="Skip stale symbols instead of failing.")
    args = ap.parse_args()

    # positions
    pos = pd.read_csv(args.positions_csv)
    if "symbol" not in pos.columns or "target_position" not in pos.columns:
        raise ValueError("positions.csv must have columns: symbol,target_position")
    pos["symbol"] = pos["symbol"].astype(str).str.strip()

    # --- Read contracts with defensive cleansing ---
    specs_raw = pd.read_csv(args.contracts_csv)
    specs_raw.columns = [str(c).strip() for c in specs_raw.columns]
    if "symbol" not in specs_raw.columns:
        raise ValueError("contracts.csv must contain 'symbol' column")

    specs_raw = specs_raw.dropna(how="all").copy()
    specs_raw["symbol"] = specs_raw["symbol"].astype(str).str.strip()
    specs_raw = specs_raw[specs_raw["symbol"] != ""]
    specs_raw = specs_raw.drop_duplicates(subset="symbol", keep="last")

    # Make sure expected columns exist
    for col, dflt in [
        ("mt5_symbol", None),
        ("contract_size", 1.0),
        ("lot_step", 0.01),
        ("lot_min", 0.0),
        ("lot_max", 1e9),
        ("px_mult", 1.0),
    ]:
        if col not in specs_raw.columns:
            specs_raw[col] = dflt

    # numeric coercion + fillna
    for nc in ["contract_size", "lot_step", "lot_min", "lot_max", "px_mult"]:
        specs_raw[nc] = pd.to_numeric(specs_raw[nc], errors="coerce")
    specs_raw["mt5_symbol"] = specs_raw["mt5_symbol"].fillna(specs_raw["symbol"])
    specs_raw["contract_size"] = specs_raw["contract_size"].fillna(1.0)
    specs_raw["lot_step"] = specs_raw["lot_step"].fillna(0.01)
    specs_raw["lot_min"] = specs_raw["lot_min"].fillna(0.0)
    specs_raw["lot_max"] = specs_raw["lot_max"].fillna(1e9)
    specs_raw["px_mult"] = specs_raw["px_mult"].fillna(1.0)

    specs = specs_raw.set_index("symbol")

    # --- build price map & staleness ---
    prices = {}
    age_days_map = {}
    to_keep = []

    for _, row in pos.iterrows():
        sym = row["symbol"]
        if sym not in specs.index:
            raise RuntimeError(f"Symbol '{sym}' missing in contracts: {args.contracts_csv}")

        c = specs.loc[sym]
        sym_mt5 = str(c.get("mt5_symbol", sym)).strip()

        # px_mult: allow comments in file (e.g., "50  # note")
        raw_px_mult = str(c.get("px_mult", "1")).strip()
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw_px_mult)
        px_mult = float(m.group(0)) if m else 1.0

        ref_px, ts = load_last_close(Path(args.prices_folder), sym)

        mt5_mid = get_mt5_mid(sym_mt5)
        px_used = float(mt5_mid) if (mt5_mid is not None and mt5_mid > 0) else float(ref_px) * px_mult
        age_days = (_utc_now() - ts).days

        prices[sym] = dict(
            px_ref=float(ref_px),
            px_mult=px_mult,
            px_used=px_used,
            ts_ref=ts,
            sym_mt5=sym_mt5,
            mt5_mid=float(mt5_mid) if mt5_mid is not None else None,
        )
        age_days_map[sym] = age_days
        to_keep.append(sym)

    # staleness preflight
    bad_syms = [s for s, d in age_days_map.items() if d > args.max_price_age_days]
    if bad_syms:
        if args.skip_stale:
            print(f"WARNING: skipping stale symbols (>{args.max_price_age_days}d): {bad_syms}")
            pos = pos[~pos["symbol"].isin(bad_syms)]
        else:
            raise RuntimeError(f"Price staleness preflight failed for {bad_syms}")

    # sanity check vs MT5 (bps deviation)
    dev_rows = []
    for sym in pos["symbol"]:
        d = prices[sym]
        if d["mt5_mid"] is None:
            continue
        ref_scaled = d["px_ref"] * d["px_mult"]
        dev_bps = abs((d["mt5_mid"] / ref_scaled) - 1.0) * 1e4
        if dev_bps > args.max_dev_bps:
            dev_rows.append([sym, round(dev_bps, 2), ref_scaled, d["mt5_mid"]])
    if dev_rows:
        print(f"MT5 price sanity WARN (bps deviation > {args.max_dev_bps}):")
        print("symbol dev_bps px_ref_scaled px_mt5")
        for r in dev_rows:
            print("%-6s %8.2f %12.6f %12.6f" % tuple(r))

    # build orders
    rows = []
    gross_abs = 0.0
    for _, row in pos.iterrows():
        sym = row["symbol"]
        target = float(row["target_position"])
        c = specs.loc[sym]
        d = prices[sym]

        contract_size = float(c["contract_size"])
        lot_step = float(c["lot_step"])
        px_used = float(d["px_used"])

        notional = target * args.nav
        lots = notional / (contract_size * px_used)
        lots_rounded = round(lots / lot_step) * lot_step

        rows.append(dict(
            symbol=sym,
            target_position=target,
            px=px_used,
            notional_usd=notional,
            lots=lots_rounded
        ))
        gross_abs += abs(notional)

    # gross cap scaling
    scale = 1.0
    cap = args.nav * args.gross_cap
    if gross_abs > cap:
        scale = cap / gross_abs
        for r in rows:
            r["target_position"] *= scale
            r["notional_usd"] *= scale
            r["lots"] *= scale

    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out_csv, index=False)
    print(f"Saved orders to {args.out_csv} | gross before scale: {gross_abs:,.0f} | scale: {scale:.3f}")


if __name__ == "__main__":
    main()