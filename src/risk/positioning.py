import numpy as np
import pandas as pd


def target_units(
    equity: float,
    sleeve_target_ann_vol: float,
    px: pd.Series,
    vol_series: pd.Series,
    per_trade_risk_cap: float,
) -> pd.Series:
    sigma = vol_series.replace(0, np.nan).ffill().bfill()
    units = (sleeve_target_ann_vol / sigma) * (equity / px)
    # cap by per-trade risk (placeholder, refined later)
    return units.fillna(0)
