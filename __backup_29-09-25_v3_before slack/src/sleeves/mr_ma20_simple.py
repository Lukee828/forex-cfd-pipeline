import pandas as pd
import numpy as np

def signals_daily(df: pd.DataFrame, z_in=1.5, z_out=0.5, ttl=10) -> pd.Series:
    """
    df: daily with Close; returns side series (+1/-1/0)
    Entry when |z| >= z_in; Exit to flat when |z| < z_out or ttl bars.
    """
    px = df['Close']
    ma = px.rolling(20, min_periods=10).mean()
    ret = px.pct_change()
    sd = ret.rolling(20, min_periods=10).std().replace(0, np.nan)
    z = (px/ma - 1.0) / sd

    side = pd.Series(0, index=df.index, dtype=float)
    dirn = 0
    bars = 0
    for ts in df.index:
        if dirn == 0:
            if z.get(ts, np.nan) <= -z_in:
                dirn = 1
                bars = 0
            elif z.get(ts, np.nan) >= z_in:
                dirn = -1
                bars = 0
        else:
            bars += 1
            if abs(z.get(ts, np.nan)) < z_out or bars >= ttl:
                dirn = 0
                bars = 0
        side.loc[ts] = dirn
    return side
