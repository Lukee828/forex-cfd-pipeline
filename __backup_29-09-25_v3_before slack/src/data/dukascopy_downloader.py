
"""
Dukascopy downloader (uses pip package `dukascopy-python` if present; also tries `dukascopy`).
If the exact API differs in your environment, see the adapter notes below.

CLI examples:
  # 1H bars (pull m1, resample to 1h)
  python -m src.data.dukascopy_downloader --symbol EURUSD --tf 1h --start 2022-01-01 --end 2022-12-31 --out data/prices_1h/EURUSD.parquet

  # 1D bars (pull m1, resample to 1d)
  python -m src.data.dukascopy_downloader --symbol XAUUSD --tf 1d --start 2020-01-01 --end 2024-12-31 --out data/prices_1d/XAUUSD.parquet

Notes:
- We fetch 1-minute data and resample to target TF for consistency.
- Package detection order:
    1) `dukascopy_python`  (installed via `pip install dukascopy-python`)
    2) `dukascopy`
- If neither is available or the API differs, we print a clear hint to edit `_fetch_with_library`.
"""
import argparse, pathlib, pandas as pd, sys

def _normalize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    import pandas as pd
    import numpy as np

    # 1) Find timestamp (column or index)
    time_col = None
    for cand in ["Date", "date", "timestamp", "time", "datetime"]:
        if cand in df.columns:
            time_col = cand
            break

    if time_col is not None:
        idx = pd.to_datetime(df[time_col], utc=True, errors="coerce")
        df = df.drop(columns=[time_col])
    elif isinstance(df.index, pd.DatetimeIndex):
        idx = df.index
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
    else:
        raise ValueError("No datetime found: expected a Date/time/timestamp column or a DatetimeIndex")

    # 2) Map OHLC(V) with multiple possible namings
    def pick(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    # Try BID → plain → ASK naming
    o = pick("bidopen", "open", "askopen", "Open")
    h = pick("bidhigh", "high", "askhigh", "High")
    l = pick("bidlow",  "low",  "asklow",  "Low")
    c = pick("bidclose","close","askclose","Close")
    v = pick("volume", "Volume", "vol")

    missing = [n for n,x in zip(["Open","High","Low","Close"], [o,h,l,c]) if x is None]
    if missing:
        raise ValueError(f"Missing OHLC columns in downloaded data: {missing}. "
                         f"Got columns: {list(df.columns)}")

    if v is None:
        df["__Volume__"] = 0.0
        v = "__Volume__"

    out = pd.DataFrame({
        "Open":  df[o].astype(float),
        "High":  df[h].astype(float),
        "Low":   df[l].astype(float),
        "Close": df[c].astype(float),
        "Volume":df[v].astype(float),
    }, index=idx)

    # 3) Clean & finalize
    out = out.sort_index()
    # Drop flat zero-volume bars (weekends)
    mask = ~((out["High"]==out["Low"]) & (out["Open"]==out["Close"]) & (out["Volume"]==0))
    out = out[mask]
    out["symbol"] = symbol
    return out[["Open","High","Low","Close","Volume","symbol"]]


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    tf = tf.lower()
    rule = {'1m':'1min','5m':'5min','1h':'1H','1d':'1D'}.get(tf)
    if rule is None:
        raise ValueError("Unsupported tf; choose from 1m,5m,1h,1d")
    o = df['Open'].resample(rule).first()
    h = df['High'].resample(rule).max()
    l = df['Low'].resample(rule).min()
    c = df['Close'].resample(rule).last()
    v = df['Volume'].resample(rule).sum()
    sym = df['symbol'].resample(rule).last()
    out = pd.concat([o,h,l,c,v,sym], axis=1)
    out.columns = ['Open','High','Low','Close','Volume','symbol']
    return out.dropna(how='any')

def _save_parquet(df: pd.DataFrame, out_path: str):
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)

def _try_import_library():
    try:
        import dukascopy_python as duka  # pip name: dukascopy-python
        return ('dukascopy_python', duka)
    except Exception:
        try:
            import dukascopy as duka
            return ('dukascopy', duka)
        except Exception:
            return (None, None)

def _fetch_with_library(symbol: str, start: str, end: str):
    import pandas as pd
    import dukascopy_python as dpy

    # --- helpers ------------------------------------------------------------
    def pick_attr(mod, names, required=True):
        for n in names:
            if hasattr(mod, n):
                return getattr(mod, n)
        if required:
            raise AttributeError(f"None of {names} found on {mod.__name__}")
        return None

    # interval constants across versions
    def interval_const(tf: str):
        tf = tf.lower()
        if tf == "1m":
            return pick_attr(dpy, ["INTERVAL_MIN_1","INTERVAL_M1","INTERVAL_1_MIN"])
        if tf == "5m":
            return pick_attr(dpy, ["INTERVAL_MIN_5","INTERVAL_M5","INTERVAL_5_MIN"])
        if tf == "1h":
            return pick_attr(dpy, ["INTERVAL_HOUR_1","INTERVAL_H1","INTERVAL_1_HOUR"])
        if tf == "1d":
            return pick_attr(dpy, ["INTERVAL_DAY_1","INTERVAL_D1","INTERVAL_1_DAY"])
        raise ValueError("Unsupported tf")

    # offer side across versions
    def offer_side_bid():
        return pick_attr(dpy, ["OFFER_SIDE_BID","BID","BID_SIDE"], required=False)

    # try to find the instrument constant by name
    def resolve_instrument(sym: str):
        from dukascopy_python import instruments as inst
        s = sym.upper()
        candidates = dir(inst)
        # common patterns: EUR_USD, FX_MAJORS_EUR_USD, EURUSD, etc.
        want_parts = [s[:3], s[3:]]  # ['EUR','USD']
        ranked = []
        for name in candidates:
            up = name.upper()
            score = 0
            if all(p in up for p in want_parts):
                score += 2
            if s in up or "_".join(want_parts) in up:
                score += 1
            if "FX" in up:
                score += 0.5
            if score > 0:
                ranked.append((score, name))
        if not ranked:
            raise SystemExit(
                f"Could not resolve instrument for '{sym}'. Inspect dukascopy_python.instruments"
            )
        ranked.sort(reverse=True)
        return getattr(inst, ranked[0][1])

    # --- fetch m1 and let our pipeline resample -----------------------------
    inst_const = resolve_instrument(symbol)
    iv_m1 = interval_const("1m")
    bid_side = offer_side_bid()

    start_dt = pd.Timestamp(start, tz="UTC")
    end_dt   = pd.Timestamp(end,   tz="UTC")

    # fetch() signature is stable: fetch(instrument=..., interval=..., offer_side=..., start=..., end=...)
    kwargs = dict(instrument=inst_const, interval=iv_m1, start=start_dt, end=end_dt)
    if bid_side is not None:
        kwargs["offer_side"] = bid_side

    df = dpy.fetch(**kwargs)

    # Standardize columns -> our pipeline
    if "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "Date"})
    elif "time" in df.columns:
        df = df.rename(columns={"time": "Date"})
    # Normalize OHLCV naming if lowercase
    ren = {"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}
    df = df.rename(columns={k:v for k,v in ren.items() if k in df.columns})
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", default="1h", choices=["1m","5m","1h","1d"])
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", required=True, help="Parquet path, e.g. data/prices_1h/EURUSD.parquet")
    args = ap.parse_args()

    raw_m1 = _fetch_with_library(args.symbol, args.start, args.end)
    norm   = _normalize(raw_m1, args.symbol)
    if args.tf.lower() != "1m":
        norm = _resample(norm, args.tf)
    _save_parquet(norm, args.out)
    print(f"Saved {len(norm):,} bars -> {args.out}")

if __name__ == "__main__":
    main()
