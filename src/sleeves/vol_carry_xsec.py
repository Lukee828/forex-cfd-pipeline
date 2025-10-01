import pandas as pd
import numpy as np


def signals_xsec_volcarry(
    df_map: dict, top_q: float = 0.35, bot_q: float = 0.35, lookback=21 * 3
) -> dict:
    symbols = list(df_map.keys())
    close = (
        pd.concat([df_map[s]["Close"].rename(s) for s in symbols], axis=1)
        .sort_index()
        .ffill()
    )
    vol = close.pct_change().rolling(lookback, min_periods=lookback // 2).std()
    last_of_month = {}
    for ts in close.index:
        key = (ts.year, ts.month)
        if key not in last_of_month or ts > last_of_month[key]:
            last_of_month[key] = ts
    month_end_set = sorted(last_of_month.values())
    sigs = {s: pd.Series(0.0, index=close.index) for s in symbols}
    for dt in month_end_set:
        row = vol.loc[dt].dropna()
        if row.empty:
            continue
        q_lo = row.quantile(top_q)
        q_hi = row.quantile(1 - bot_q)
        longs = row[row <= q_lo].index
        shorts = row[row >= q_hi].index
        for s in symbols:
            sigs[s].loc[dt] = 1.0 if s in longs else (-1.0 if s in shorts else 0.0)
    for s in symbols:
        mask = pd.Series(False, index=close.index)
        mask.loc[month_end_set] = True
        sigs[s] = sigs[s].where(mask, np.nan).ffill().fillna(0.0)
    return sigs
