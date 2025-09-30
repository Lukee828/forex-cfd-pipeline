import pandas as pd
from .base import OrderIntent

PRIORITY = 100

def signals(df_d: pd.DataFrame, lookbacks=(40,55,80,100), exit_bars=80, symbols=None):
    intents = []
    for sym, sdf in df_d.groupby("symbol"):
        if symbols and sym not in symbols: 
            continue
        hi = sdf["High"].rolling(min(lookbacks)).max()
        lo = sdf["Low"].rolling(min(lookbacks)).min()
        brkup = sdf["Close"] > hi.shift(1)
        brkdwn = sdf["Close"] < lo.shift(1)
        for ts, up, dn in zip(sdf.index, brkup, brkdwn):
            if up:
                intents.append(OrderIntent(ts, sym, "long", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":exit_bars}, "tsmom", PRIORITY, 1.0))
            elif dn:
                intents.append(OrderIntent(ts, sym, "short", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":exit_bars}, "tsmom", PRIORITY, 1.0))
    return intents
