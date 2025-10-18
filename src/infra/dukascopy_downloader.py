# src/infra/dukascopy_downloader.py
# Non-breaking Dukascopy downloader (+resample) with a small API that downstream can rely on.

from __future__ import annotations
import pathlib
import pandas as pd


def _normalize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    import pandas as pd

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
        raise ValueError(
            "No datetime found: expected a Date/time/timestamp column or a DatetimeIndex"
        )

    def pick(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    o = pick("bidopen", "open", "askopen", "Open")
    h = pick("bidhigh", "high", "askhigh", "High")
    lo = pick("bidlow", "low", "asklow", "Low")
    c = pick("bidclose", "close", "askclose", "Close")
    v = pick("volume", "Volume", "vol")

    missing = [n for n, col in zip(["Open", "High", "Low", "Close"], [o, h, lo, c]) if col is None]
    if missing:
        raise ValueError(
            f"Missing OHLC columns in downloaded data: {missing}. Got columns: {list(df.columns)}"
        )

    if v is None:
        df["__Volume__"] = 0.0
        v = "__Volume__"

    out = pd.DataFrame(
        {
            "Open": df[o].astype(float),
            "High": df[h].astype(float),
            "Low": df[lo].astype(float),
            "Close": df[c].astype(float),
            "Volume": df[v].astype(float),
        },
        index=pd.DatetimeIndex(idx, tz="UTC"),
    ).sort_index()

    mask = ~((out["High"] == out["Low"]) & (out["Open"] == out["Close"]) & (out["Volume"] == 0))
    out = out[mask]
    out["symbol"] = symbol
    return out[["Open", "High", "Low", "Close", "Volume", "symbol"]]


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    tf = tf.lower()
    rule = {"1m": "1min", "5m": "5min", "1h": "1H", "1d": "1D"}.get(tf)
    if rule is None:
        raise ValueError("Unsupported tf; choose from 1m,5m,1h,1d")
    o = df["Open"].resample(rule).first()
    h = df["High"].resample(rule).max()
    lo = df["Low"].resample(rule).min()
    c = df["Close"].resample(rule).last()
    v = df["Volume"].resample(rule).sum()
    s = df["symbol"].resample(rule).last()
    out = pd.concat([o, h, lo, c, v, s], axis=1)
    out.columns = ["Open", "High", "Low", "Close", "Volume", "symbol"]
    return out.dropna(how="any")


def _fetch_with_library(symbol: str, start: str, end: str) -> pd.DataFrame:
    import pandas as pd

    try:
        import dukascopy_python as dpy
    except Exception as e:
        raise SystemExit("dukascopy-python not installed. Try: pip install dukascopy-python") from e

    def pick_attr(mod, names, required=True):
        for n in names:
            if hasattr(mod, n):
                return getattr(mod, n)
        if required:
            raise AttributeError(f"None of {names} found on {mod.__name__}")
        return None

    def interval_const(tf: str):
        tf = tf.lower()
        if tf == "1m":
            return pick_attr(dpy, ["INTERVAL_MIN_1", "INTERVAL_M1", "INTERVAL_1_MIN"])
        if tf == "5m":
            return pick_attr(dpy, ["INTERVAL_MIN_5", "INTERVAL_M5", "INTERVAL_5_MIN"])
        if tf == "1h":
            return pick_attr(dpy, ["INTERVAL_HOUR_1", "INTERVAL_H1", "INTERVAL_1_HOUR"])
        if tf == "1d":
            return pick_attr(dpy, ["INTERVAL_DAY_1", "INTERVAL_D1", "INTERVAL_1_DAY"])
        raise ValueError("Unsupported tf")

    def offer_side_bid():
        return pick_attr(dpy, ["OFFER_SIDE_BID", "BID", "BID_SIDE"], required=False)

    def resolve_instrument(sym: str):
        from dukascopy_python import instruments as inst

        s = sym.upper()
        want_parts = [s[:3], s[3:]]
        ranked = []
        for name in dir(inst):
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

    inst_const = resolve_instrument(symbol)
    iv_m1 = interval_const("1m")
    bid_side = offer_side_bid()
    start_dt = pd.Timestamp(start, tz="UTC")
    end_dt = pd.Timestamp(end, tz="UTC")

    kwargs = dict(instrument=inst_const, interval=iv_m1, start=start_dt, end=end_dt)
    if bid_side is not None:
        kwargs["offer_side"] = bid_side

    df = dpy.fetch(**kwargs)

    if "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "Date"})
    elif "time" in df.columns:
        df = df.rename(columns={"time": "Date"})

    ren = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    return df


def download_ohlcv(symbol: str, start: str, end: str, tf: str = "1h") -> pd.DataFrame:
    raw_m1 = _fetch_with_library(symbol, start, end)
    norm = _normalize(raw_m1, symbol)
    if tf.lower() != "1m":
        norm = _resample(norm, tf)
    return norm


def save_symbol(symbol: str, start: str, end: str, tf: str, out_dir: str) -> str:
    df = download_ohlcv(symbol, start, end, tf)
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(out_dir) / f"{symbol}_{tf.lower()}.parquet"
    df.to_parquet(out)
    return str(out)
