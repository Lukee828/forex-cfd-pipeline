# src/research/wfo.py
"""
Purged Walk-Forward:
- split index into folds with embargo (purging leakage)
- for each fold: train params -> validate -> roll.
This is a scaffold; you plug strategy param search inside `fit_params`.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class Fold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def make_purged_folds(index: pd.DatetimeIndex, n_folds=5, embargo_days=5) -> list[Fold]:
    idx = index.unique().sort_values()
    n = len(idx)
    splits = np.linspace(0, n, n_folds + 1).astype(int)
    folds = []
    for i in range(n_folds):
        a, b = splits[i], splits[i + 1]
        test = idx[a:b]
        train = idx[: max(0, a - embargo_days)]
        if len(test) == 0 or len(train) == 0:
            continue
        folds.append(Fold(train[0], train[-1], test[0], test[-1]))
    return folds


def fit_params(train_df):
    # TODO: grid/random search for strategy params based on train_df performance
    return {"tf_lookback": 50, "order_size": 0.1}


def run_wfo(ohlcv_by_sym: dict[str, pd.DataFrame]):
    # unify time index
    idx = sorted(set().union(*[df.index for df in ohlcv_by_sym.values()]))
    idx = pd.DatetimeIndex(idx)
    folds = make_purged_folds(idx, n_folds=5, embargo_days=5)
    results = []
    for f in folds:
        # slice train/test views
        train = {
            s: df.loc[f.train_start : f.train_end] for s, df in ohlcv_by_sym.items()
        }
        _test = {s: df.loc[f.test_start : f.test_end] for s, df in ohlcv_by_sym.items()}
        params = fit_params(train)
        # TODO: run backtest on test with params
        results.append({"fold": f, "params": params, "metric": np.nan})
    return pd.DataFrame(results)
