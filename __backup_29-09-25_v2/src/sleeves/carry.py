from .base import OrderIntent
import pandas as pd

PRIORITY = 50

def signals(swaps: pd.DataFrame, dxy_vol: pd.Series, top_n=3, symbols=None):
    # swaps: columns ['symbol','swap_long']
    # pick top/bottom by swap_long
    s = swaps.dropna(subset=['swap_long']).groupby('symbol')['swap_long'].last().sort_values(ascending=False)
    longs = list(s.head(top_n).index)
    shorts = list(s.tail(top_n).index)
    intents = []
    ts = swaps['ts_utc'].max() if 'ts_utc' in swaps.columns else pd.Timestamp.utcnow()
    for sym in longs + shorts:
        if symbols and sym not in symbols: 
            continue
        side = "long" if sym in longs else "short"
        intents.append(OrderIntent(ts, sym, side, {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":None}, "carry", PRIORITY, 1.0))
    return intents
