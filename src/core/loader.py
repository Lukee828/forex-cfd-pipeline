import pandas as pd, pathlib

def load_csv(path: str, symbol: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.rename(columns={
        "Open":"Open","High":"High","Low":"Low","Close":"Close","Volume":"Volume"
    })
    df["symbol"] = symbol
    df = df.set_index("Date").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df[["Open","High","Low","Close","Volume","symbol"]]

def save_parquet(df: pd.DataFrame, out_path: str):
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)

def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)
