import pandas as pd
from .base import OrderIntent

PRIORITY = 80


def signals(df_5m: pd.DataFrame, or_minutes=30, arm_series: pd.Series = None):
    # Simplified: place market entries at breakout time (placeholder)
    intents = []
    if arm_series is None:
        arm_series = pd.Series(False, index=df_5m.index)
    for ts, arm in arm_series.items():
        if not arm:
            continue
        sym = df_5m.loc[ts, "symbol"] if "symbol" in df_5m.columns else "SYMBOL"
        intents.append(
            OrderIntent(
                ts,
                sym,
                "long",
                {"type": "mkt", "price": None},
                {"tp": None, "sl": None, "ttl_bars": 1},
                "orb",
                PRIORITY,
                1.0,
            )
        )
    return intents
