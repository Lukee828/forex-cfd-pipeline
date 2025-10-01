import pandas as pd
import numpy as np


def realized_vol(close: pd.Series, lookback=20, annualize_on="1d") -> pd.Series:
    r = close.pct_change().rolling(lookback).std()
    ann = {
        "1d": np.sqrt(252),
        "1h": np.sqrt(252 * 24),
        "5m": np.sqrt(252 * 24 * 12),
    }.get(annualize_on, np.sqrt(252))
    return r * ann


def adr(high: pd.Series, low: pd.Series, lookback=20) -> pd.Series:
    tr = (high - low).abs()
    return tr.rolling(lookback).mean()


def vwap_session(df: pd.DataFrame, session_id: pd.Series) -> pd.Series:
    # expects columns: 'Close','Volume'
    g = df.assign(v=df["Close"] * df["Volume"]).groupby(session_id)
    vwap = g["v"].cumsum() / g["Volume"].cumsum()
    return vwap


def zscore(series: pd.Series, lb=20, robust=False) -> pd.Series:
    if robust:
        med = series.rolling(lb).median()
        mad = (series - med).abs().rolling(lb).median().replace(0, np.nan)
        return (series - med) / (1.4826 * mad)
    mu = series.rolling(lb).mean()
    sd = series.rolling(lb).std().replace(0, np.nan)
    return (series - mu) / sd
