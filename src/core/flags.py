import pandas as pd


def is_nr7(tr: pd.Series, lb=7) -> pd.Series:
    rolling_min = tr.rolling(lb).min()
    return tr.eq(rolling_min)


def is_inside_day(high: pd.Series, low: pd.Series) -> pd.Series:
    h1 = high.shift(1)
    l1 = low.shift(1)
    return (high <= h1) & (low >= l1)
