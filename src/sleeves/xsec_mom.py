import pandas as pd
from .base import OrderIntent

PRIORITY = 90

def signals(ret_12m: pd.Series, ret_1m: pd.Series, top_q=0.3, bot_q=0.3):
    score = ret_12m - ret_1m
    q_hi = score.quantile(1-top_q)
    q_lo = score.quantile(bot_q)
    longs = score[score >= q_hi].index
    shorts = score[score <= q_lo].index
    ts = pd.Timestamp.utcnow()
    intents = []
    for sym in longs:
        intents.append(OrderIntent(ts, sym, "long", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":None}, "xsec", PRIORITY, 1.0))
    for sym in shorts:
        intents.append(OrderIntent(ts, sym, "short", {"type":"mkt","price":None}, {"tp":None,"sl":None,"ttl_bars":None}, "xsec", PRIORITY, 1.0))
    return intents
