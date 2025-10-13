import pandas as pd
import numpy as np


def signals_monthly(df_map: dict, top_q: float = 0.3, bot_q: float = 0.3) -> dict:
    """
    df_map: {symbol: daily DataFrame with ['Close'] indexed by tz-aware DatetimeIndex}
    Returns: {symbol: Series (+1/-1/0)} at month-end timestamps (ffilled between rebalances).
    Score: (12m - 1m) momentum to avoid short-term reversal.
    """
    symbols = list(df_map.keys())
    panel = pd.concat([df_map[s]["Close"].rename(s) for s in symbols], axis=1).sort_index().ffill()

    r_12m = panel / panel.shift(21 * 12) - 1.0
    r_1m = panel / panel.shift(21) - 1.0
    score = r_12m - r_1m

    # tz-safe last trading timestamp of each (year, month)
    last_of_month = {}
    for ts in panel.index:
        key = (ts.year, ts.month)
        if key not in last_of_month or ts > last_of_month[key]:
            last_of_month[key] = ts
    month_end_set = set(last_of_month.values())

    signals = {s: pd.Series(0.0, index=panel.index) for s in symbols}
    for dt in sorted(month_end_set):
        sc = score.loc[dt].dropna()
        if sc.empty:
            continue
        q_hi = sc.quantile(1 - top_q)
        q_lo = sc.quantile(bot_q)
        longs = sc[sc >= q_hi].index
        shorts = sc[sc <= q_lo].index
        for s in symbols:
            signals[s].loc[dt] = 1.0 if s in longs else (-1.0 if s in shorts else 0.0)

    for s in symbols:
        mask = pd.Series(False, index=panel.index)
        mask.loc[list(month_end_set)] = True
        signals[s] = signals[s].where(mask, np.nan).ffill().fillna(0.0)

    return signals
