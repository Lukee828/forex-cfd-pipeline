from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import math
import numpy as np
import pandas as pd

@dataclass
class MetaAllocatorConfig:
    use_bayesian: bool = False
    half_life: int = 10
    min_weight: float = 0.0
    max_weight: float = 1.0
    normalize: bool = True
    include_dd: bool = True
    include_vol: bool = False  # keep simple by default
    target_vol_annual: float = 0.20
    trading_days: int = 252

class MetaAllocator:
    """Score sleeves and produce normalized weights. Expects a DataFrame with columns:
       - sharpe (float, higher is better)
       - dd (optional, 0..1 drawdown depth)
       - vol_ann (optional, annualized vol for optional throttle)
       Optionally pass a Series/dict risk_scale per sleeve to modulate weights."""

    def __init__(self, cfg: Optional[MetaAllocatorConfig] = None):
        self.cfg = cfg or MetaAllocatorConfig()

    def compute_weights(self, df: pd.DataFrame, risk_scale: Optional[pd.Series | Dict[str, float]] = None) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)
        x = df.copy()
        # base score ~ positive Sharpe only
        score = x["sharpe"].clip(lower=0.0).astype(float)
        # optional DD penalty
        if self.cfg.include_dd and "dd" in x.columns:
            ddp = (1.0 - x["dd"].clip(lower=0.0, upper=1.0).astype(float))
            score = score * ddp
        # optional vol throttle
        if self.cfg.include_vol and "vol_ann" in x.columns:
            tv = float(self.cfg.target_vol_annual)
            with np.errstate(divide="ignore", invalid="ignore"):
                vol_scale = np.where(x["vol_ann"] > 0, np.minimum(1.0, tv / x["vol_ann"]), 1.0)
            score = score * pd.Series(vol_scale, index=x.index, dtype=float)
        # risk governor scale
        if risk_scale is not None:
            rs = risk_scale if isinstance(risk_scale, pd.Series) else pd.Series(risk_scale, dtype=float)
            rs = rs.reindex(index=x.index).fillna(1.0).astype(float)
            score = score * rs
        # clamp per-sleeve
        score = score.clip(lower=self.cfg.min_weight, upper=self.cfg.max_weight)
        # normalize
        if self.cfg.normalize:
            s = float(score.sum())
            if s > 0.0:
                score = score / s
            else:
                # nothing positive: equal-weight fallback
                score = pd.Series(np.ones(len(score)) / len(score), index=score.index)
        return score.astype(float)

def ewma(series: pd.Series, half_life: int) -> pd.Series:
    if len(series) == 0:
        return series
    alpha = 1.0 - math.exp(math.log(0.5) / max(1, half_life))
    return series.ewm(alpha=alpha, adjust=False).mean()
