import os, json
from typing import List, Optional
import numpy as np
import pandas as pd
import duckdb
from alpha_factory.datafeeds.mt5_feed import MT5

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def build_features(df: pd.DataFrame, period_rsi: int = 14) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "open","high","low","close","tick_volume","spread","real_volume",
            "ret","ema20","ema50","rsi14","vol20"
        ])
    out = df.copy()
    out["ret"] = np.log(out["close"]).diff()
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["rsi14"] = rsi(out["close"], period=period_rsi)
    out["vol20"] = out["ret"].rolling(20).std()
    return out

def write_parquet(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=True)
    return os.path.abspath(path)

def write_duckdb(df: pd.DataFrame, db_path: str, table: str = "features") -> str:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = duckdb.connect(db_path)
    try:
        dfw = df.reset_index().rename(columns={"time":"ts"})
        cols = ["ts","symbol","timeframe","open","high","low","close",
                "tick_volume","spread","real_volume","ret","ema20","ema50","rsi14","vol20"]
        for c in cols:
            if c not in dfw.columns:
                dfw[c] = np.nan
        dfw = dfw[cols]
        dfw["ts"] = pd.to_datetime(dfw["ts"])

        ddl = (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "ts TIMESTAMP, "
            "symbol TEXT, "
            "timeframe TEXT, "
            "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, "
            "tick_volume BIGINT, spread BIGINT, real_volume BIGINT, "
            "ret DOUBLE, ema20 DOUBLE, ema50 DOUBLE, rsi14 DOUBLE, vol20 DOUBLE)"
        )
        con.execute(ddl)
        con.register("df_temp", dfw)
        con.execute(f"INSERT INTO {table} SELECT * FROM df_temp")
    finally:
        con.close()
    return os.path.abspath(db_path)

def run(symbols: List[str], timeframe: str, count: Optional[int],
        dt_from: Optional[str], dt_to: Optional[str],
        out_parquet_dir: Optional[str], out_duckdb: Optional[str]) -> dict:
    api = MT5()
    results = {}
    for sym in symbols:
        if count is not None:
            bars = api.copy_rates_df(sym, timeframe=timeframe, count=int(count))
        else:
            bars = api.copy_rates_range_df(sym, timeframe=timeframe, dt_from=dt_from, dt_to=dt_to)
        feat = build_features(bars)
        feat["symbol"] = sym
        feat["timeframe"] = timeframe
        wrote = {}
        if out_parquet_dir:
            p = os.path.join(out_parquet_dir, f"{sym}_{timeframe}.parquet")
            wrote["parquet"] = write_parquet(feat, p)
        if out_duckdb:
            wrote["duckdb"] = write_duckdb(
                feat[["open","high","low","close","tick_volume","spread","real_volume","ret","ema20","ema50","rsi14","vol20","symbol","timeframe"]],
                out_duckdb
            )
        results[sym] = {"rows": int(len(feat)), "outputs": wrote}
    return results

def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["XAUUSD","US30","DE40"])
    ap.add_argument("--timeframe", default="M5")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--count", type=int, help="last N bars")
    grp.add_argument("--from_dt", help="YYYY-MM-DD or ISO start (with --to_dt)")
    ap.add_argument("--to_dt", help="YYYY-MM-DD or ISO end")
    ap.add_argument("--out_parquet_dir", default="data/features")
    ap.add_argument("--out_duckdb", default="data/feature_store.duckdb")
    a = ap.parse_args()
    if a.from_dt and not a.to_dt:
        ap.error("--from_dt requires --to_dt")
    res = run(a.symbols, a.timeframe, a.count, a.from_dt, a.to_dt, a.out_parquet_dir, a.out_duckdb)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    _cli()