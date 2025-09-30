import pandas as pd
from .base import OrderIntent

PRIORITY = 70

def signals(df_1h: pd.DataFrame, session_id: pd.Series, atr: pd.Series, z_series: pd.Series, z_level=2.0):
    intents = []
    quiet = atr < atr.rolling(90*24).median()
    for (ts, row), z, q in zip(df_1h.iterrows(), z_series, quiet):
        if not q or pd.isna(z): 
            continue
        sym = row['symbol']
        if z <= -z_level:
            intents.append(OrderIntent(ts, sym, "long", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":6}, "mr_vwap", PRIORITY, 1.0))
        elif z >= z_level:
            intents.append(OrderIntent(ts, sym, "short", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":6}, "mr_vwap", PRIORITY, 1.0))
    return intents
