# src/risk/vol_state.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

Regime = Literal["LOW", "MEDIUM", "HIGH"]


def _ann_factor(freq: Optional[str] = None) -> float:
    # Simple annualization root factors; fallback to sqrt(252)
    if freq:
        f = freq.lower()
        if "d" in f:  # daily
            return float(np.sqrt(252.0))
        if "h" in f:  # hourly
            return float(np.sqrt(24.0 * 252.0))
        if "min" in f:  # minute
            return float(np.sqrt(390.0 * 252.0))  # US cash minutes
    return float(np.sqrt(252.0))


def _pct_change(close: pd.Series) -> pd.Series:
    # avoid pandas deprecation on fill_method default
    return close.pct_change(fill_method=None)


def rolling_vol(close: pd.Series, window: int = 20, freq_hint: Optional[str] = None) -> pd.Series:
    """
    Rolling realized volatility (close-to-close) annualized.
    """
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series (prices).")
    rets = _pct_change(close).astype(float)
    vol = rets.rolling(window=window, min_periods=max(2, int(window * 0.6))).std(ddof=0)
    return vol * _ann_factor(freq_hint)


@dataclass
class VolStateMachine:
    """
    Classify each timestamp into a volatility regime using quantile thresholds on a
    rolling volatility estimator. Thresholds can be fit on a reference sample
    (in-sample) then applied out-of-sample.
    """

    window: int = 20
    lower_q: float = 0.33
    upper_q: float = 0.66
    freq_hint: Optional[str] = None

    # learned thresholds
    low_hi: float = np.nan
    med_hi: float = np.nan

    def fit(self, close: pd.Series) -> "VolStateMachine":
        vol = rolling_vol(close, window=self.window, freq_hint=self.freq_hint).dropna()
        if vol.empty:
            raise ValueError("No volatility observations to fit thresholds.")
        self.low_hi = float(np.quantile(vol.values, self.lower_q))
        self.med_hi = float(np.quantile(vol.values, self.upper_q))
        # ensure ordering
        if not (self.low_hi <= self.med_hi):
            self.low_hi, self.med_hi = min(self.low_hi, self.med_hi), max(self.low_hi, self.med_hi)
        return self

    def classify_series(self, close: pd.Series) -> pd.Series:
        if not np.isfinite(self.low_hi) or not np.isfinite(self.med_hi):
            raise RuntimeError("VolStateMachine not fitted. Call fit() first.")
        vol = rolling_vol(close, window=self.window, freq_hint=self.freq_hint)

        # map to regimes
        def _bucket(x: float) -> Regime:
            if not np.isfinite(x):  # early NaNs before window fills
                return "MEDIUM"
            if x <= self.low_hi:
                return "LOW"
            if x <= self.med_hi:
                return "MEDIUM"
            return "HIGH"

        return vol.apply(_bucket).astype("category")


def infer_vol_regime(
    close: pd.Series,
    window: int = 20,
    lower_q: float = 0.33,
    upper_q: float = 0.66,
    freq_hint: Optional[str] = None,
) -> pd.Series:
    """
    Convenience: fit thresholds on the whole series, then classify.
    """
    vsm = VolStateMachine(window=window, lower_q=lower_q, upper_q=upper_q, freq_hint=freq_hint)
    vsm.fit(close)
    return vsm.classify_series(close)
