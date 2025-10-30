# src/alpha_factory/meta_allocator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Mapping
import math


@dataclass(frozen=True)
class AllocatorConfig:
    mode: str = "ewma"  # "ewma" | "bayes"
    half_life_days: float = 14  # EWMA half-life for metric smoothing
    min_weight: float = 0.0  # floor per sleeve
    max_weight: float = 0.9  # cap per sleeve
    normalize: bool = True  # project to simplex
    dd_penalty: float = 2.0  # penalty multiplier for drawdown
    eps: float = 1e-9


class MetaAllocator:
    """
    Turn per-sleeve meta metrics into weights.
    Expected metrics shape (per sleeve): {"sharpe": float, "dd": float}
    """

    def __init__(self, cfg: AllocatorConfig):
        self.cfg = cfg

    def _score(self, m: Mapping[str, float]) -> float:
        # Simple utility: higher sharpe better, higher DD worse
        sharpe = float(m.get("sharpe", 0.0))
        dd = max(float(m.get("dd", 0.0)), self.cfg.eps)
        return sharpe / (1.0 + self.cfg.dd_penalty * dd)

    def _cap_floor(self, w: Dict[str, float]) -> Dict[str, float]:
        out = {k: min(max(v, self.cfg.min_weight), self.cfg.max_weight) for k, v in w.items()}
        if self.cfg.normalize:
            s = sum(out.values())
            if s > self.cfg.eps:
                out = {k: v / s for k, v in out.items()}
        return out

    def allocate(self, metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
        mode = (self.cfg.mode or "ewma").lower()
        if mode == "ewma":
            return self._allocate_ewma(metrics)
        elif mode == "bayes":
            return self._allocate_bayes(metrics)
        else:
            raise ValueError(f"Unknown allocator mode: {self.cfg.mode}")

    # --- EWMA: treats scores as current “level” (no persistent state here; CI is stateless) ---
    def _allocate_ewma(self, metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
        if not metrics:
            return {}
        lam = self._lambda_from_half_life(self.cfg.half_life_days)
        # With no history here, just apply lambda as a softener on the score
        raw = {k: lam * self._score(m) for k, m in metrics.items()}
        # Ensure non-negativity
        raw = {k: max(0.0, v) for k, v in raw.items()}
        return self._cap_floor(raw)

    # --- “Bayes-lite”: score -> pseudo precision; shrink toward equal weight by uncertainty ---
    def _allocate_bayes(self, metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
        if not metrics:
            return {}
        sleeves = list(metrics.keys())
        n = len(sleeves)
        equal = 1.0 / max(1, n)

        scores = {k: max(0.0, self._score(m)) for k, m in metrics.items()}
        # Convert DD into uncertainty proxy: higher DD => lower precision
        # precision ~ 1 / (dd + eps)
        prec = {k: 1.0 / (max(float(metrics[k].get("dd", 0.0)), self.cfg.eps)) for k in sleeves}

        # Posterior mean of convex combination: (prec*score + tau*equal) / (prec + tau)
        # tau controls shrinkage toward equal-weight when precision is low
        tau = 5.0
        post = {}
        for k in sleeves:
            num = prec[k] * scores[k] + tau * equal
            den = prec[k] + tau + self.cfg.eps
            post[k] = max(0.0, num / den)

        return self._cap_floor(post)

    @staticmethod
    def _lambda_from_half_life(half_life_days: float) -> float:
        # standard EWMA relationship: lambda = 0.5**(1/HL)
        hl = max(half_life_days, 1e-6)
        return math.pow(0.5, 1.0 / hl)
