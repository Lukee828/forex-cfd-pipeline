from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def _softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    if temperature <= 0:
        raise ValueError("temperature must be > 0")
    z = (x - np.nanmax(x)) / temperature
    ez = np.exp(z - np.nanmax(z))
    s = ez / np.nansum(ez)
    return np.nan_to_num(s, nan=0.0)


@dataclass(frozen=True)
class EWMAConfig:
    window: int = 60  # (kept for future use; we use decay)
    decay: float = 0.94
    temperature: float = 1.0
    floor: float = 0.0
    cap: float = 1.0
    expand_blend: float = 0.00  # expanding Sharpe stabilizer
    expand_warmup: int = 20  # min bars for expanding stats
    global_blend: float = 1.00  # global Sharpe anchor (full-sample) replicated across time


@dataclass(frozen=True)
class BayesConfig:
    window: int = 60
    prior_mean: float = 0.0
    prior_var: float = 0.05**2
    obs_var_floor: float = 1e-6
    temperature: float = 1.0
    floor: float = 0.0
    cap: float = 1.0


class MetaAllocator:
    """
    Portfolio sleeve allocator.
    Input: returns DataFrame (index=time, columns=sleeves), values in decimal returns.
    Output: weights DataFrame summing to 1.0 each timestamp.

    Modes:
      - 'ewma': score = blend(EWMA Sharpe, expanding Sharpe, global Sharpe) → softmax → weights
      - 'bayes': simple normal-normal posterior signal-to-uncertainty → softmax → weights
    """

    def __init__(
        self,
        mode: str = "ewma",
        ewma_cfg: Optional[EWMAConfig] = None,
        bayes_cfg: Optional[BayesConfig] = None,
    ):
        assert mode in ("ewma", "bayes")
        self.mode = mode
        self.ewma_cfg = ewma_cfg or EWMAConfig()
        self.bayes_cfg = bayes_cfg or BayesConfig()

    # ---------- helpers ----------
    @staticmethod
    def _ewma(series: pd.Series, decay: float) -> pd.Series:
        alpha = 1.0 - decay
        return series.ewm(alpha=alpha, adjust=False, min_periods=1).mean()

    @staticmethod
    def _ewmstd(series: pd.Series, decay: float) -> pd.Series:
        alpha = 1.0 - decay
        return series.ewm(alpha=alpha, adjust=False, min_periods=2).std().bfill()

    # ---------- modes ----------
    def _weights_ewma(self, rets: pd.DataFrame) -> pd.DataFrame:
        cfg = self.ewma_cfg
        eps = 1e-12

        # EWMA mean/std per sleeve
        mu_ewm = rets.apply(lambda s: self._ewma(s, cfg.decay))
        sd_ewm = rets.apply(lambda s: self._ewmstd(s, cfg.decay)).clip(lower=eps)
        sharpe_ewm = (mu_ewm / sd_ewm).clip(-10, 10)

        # Expanding mean/std stabilizer
        mu_exp = rets.expanding(min_periods=cfg.expand_warmup).mean().bfill()
        sd_exp = (
            rets.expanding(min_periods=cfg.expand_warmup)
            .std()
            .bfill()
            .replace(0, np.nan)
            .fillna(eps)
        )
        sharpe_exp = (mu_exp / sd_exp).clip(-10, 10)

        # Global (full-sample) Sharpe anchor, replicated across time
        mu_g = rets.mean()
        sd_g = rets.std().replace(0, np.nan).fillna(eps)
        sharpe_g_row = (mu_g / sd_g).clip(-10, 10)
        sharpe_global = pd.DataFrame(
            np.tile(sharpe_g_row.values, (rets.shape[0], 1)), index=rets.index, columns=rets.columns
        )

        a = float(cfg.expand_blend)
        b = float(cfg.global_blend)
        base = max(0.0, 1.0 - a - b)
        score = (base * sharpe_ewm + a * sharpe_exp + b * sharpe_global).clip(-10, 10)

        w = []
        cols = rets.columns
        for t in rets.index:
            v = score.loc[t, cols].to_numpy(dtype=float)
            sm = _softmax(v, cfg.temperature)
            sm = np.clip(sm, cfg.floor, cfg.cap)
            if sm.sum() == 0:
                sm = np.ones_like(sm) / len(sm)
            else:
                sm = sm / sm.sum()
            w.append(sm)
        return pd.DataFrame(w, index=rets.index, columns=cols)

    def _weights_bayes(self, rets: pd.DataFrame) -> pd.DataFrame:
        cfg = self.bayes_cfg
        cols = rets.columns
        roll_mean = rets.rolling(cfg.window, min_periods=max(2, cfg.window // 5)).mean().bfill()
        roll_var = rets.rolling(cfg.window, min_periods=max(2, cfg.window // 5)).var().bfill()
        roll_var = roll_var.clip(lower=cfg.obs_var_floor)

        n = rets.rolling(cfg.window, min_periods=1).count().clip(lower=1.0)
        inv_var0 = 1.0 / cfg.prior_var
        mu0_term = cfg.prior_mean * inv_var0

        mu_post = (mu0_term + (n * roll_mean / roll_var)) / (inv_var0 + (n / roll_var))
        var_post = 1.0 / (inv_var0 + (n / roll_var))
        std_post = np.sqrt(var_post)

        score = (mu_post / std_post).clip(-10, 10)
        w = []
        for t in rets.index:
            v = score.loc[t, cols].to_numpy(dtype=float)
            sm = _softmax(v, cfg.temperature)
            sm = np.clip(sm, cfg.floor, cfg.cap)
            if sm.sum() == 0:
                sm = np.ones_like(sm) / len(sm)
            else:
                sm = sm / sm.sum()
            w.append(sm)
        return pd.DataFrame(w, index=rets.index, columns=cols)

    # ---------- public ----------
    def allocate(self, returns: pd.DataFrame) -> pd.DataFrame:
        rets = returns.copy().astype(float).fillna(0.0)
        if self.mode == "ewma":
            W = self._weights_ewma(rets)
        else:
            W = self._weights_bayes(rets)
        rs = W.sum(axis=1).replace(0, np.nan)
        W = W.div(rs, axis=0).fillna(1.0 / W.shape[1])
        return W
