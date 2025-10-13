import pandas as pd
from .base import OrderIntent

PRIORITY = 60


def signals(df_5m: pd.DataFrame, overlap_mask: pd.Series):
    intents = []
    for ts, ok in overlap_mask.items():
        if not ok:
            continue
        sym = df_5m.loc[ts, "symbol"] if "symbol" in df_5m.columns else "SYMBOL"
        intents.append(
            OrderIntent(
                ts,
                sym,
                "long",
                {"type": "mkt", "price": None},
                {"tp": None, "sl": None, "ttl_bars": 1},
                "seasonality",
                PRIORITY,
                0.8,
            )
        )
    return intents
