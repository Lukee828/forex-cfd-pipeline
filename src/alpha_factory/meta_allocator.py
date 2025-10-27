from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple


@dataclass
class AllocatorConfig:
    mode: str = "ewma"  # "ewma" or "bayesian" (placeholder)
    min_weight: float = 0.0
    max_weight: float = 1.0
    turnover_penalty: float = 0.02
    corr_cap: float = 0.75  # cap correlation between sleeves
    corr_governor_strength: float = 0.5  # 0..1: fraction to dampen
    ewma_alpha: float = 0.3


class MetaAllocator:
    """
    Minimal, production-friendly meta allocator with:
      * EWMA performance weighting
      * Simple correlation governor
      * Turnover penalty to discourage whipsaw

    Inputs
    ------
    metrics: Mapping[str, Mapping[str, float]]
        Per-sleeve dict with keys like "sharpe", "dd", "edge" etc.
    prev_weights: Mapping[str, float]
        Previous allocation (0..1).
    corr: Mapping[Tuple[str, str], float]
        Symmetric correlation map between sleeves; missing pairs treated as 0.0.
    """

    def __init__(self, config: Optional[AllocatorConfig] = None):
        self.cfg = config or AllocatorConfig()

    # ----------------------
    # Public API
    # ----------------------
    def allocate(
        self,
        metrics: Mapping[str, Mapping[str, float]],
        prev_weights: Optional[Mapping[str, float]] = None,
        corr: Optional[Mapping[Tuple[str, str], float]] = None,
    ) -> Dict[str, float]:
        names = list(metrics.keys())
        prev = {k: float((prev_weights or {}).get(k, 0.0)) for k in names}
        raw = (
            self._score_ewma(metrics) if self.cfg.mode == "ewma" else self._score_bayesian(metrics)
        )
        raw = self._clip(raw, self.cfg.min_weight, self.cfg.max_weight)
        raw = self._apply_corr_governor(
            raw, corr or {}, cap=self.cfg.corr_cap, strength=self.cfg.corr_governor_strength
        )
        w = self._normalize(raw)
        w = self._apply_turnover_penalty(prev, w, lam=self.cfg.turnover_penalty)
        return self._normalize(w)

    # ----------------------
    # Scoring
    # ----------------------
    def _score_ewma(self, metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
        """Score sleeves by EWMA of simple composite: sharpe - 0.2*dd."""
        a = self.cfg.ewma_alpha
        out: Dict[str, float] = {}
        for k, m in metrics.items():
            sharpe = float(m.get("sharpe", 0.0))
            dd = float(m.get("dd", 0.0))
            base = sharpe - 0.2 * dd
            prev = float(m.get("prev_score", base))
            out[k] = a * base + (1 - a) * prev
        return out

    def _score_bayesian(self, metrics: Mapping[str, Mapping[str, float]]) -> Dict[str, float]:
        # Placeholder: returns sharpe-positive sleeves; extend to calibrated probabilities later.
        out: Dict[str, float] = {}
        for k, m in metrics.items():
            sharpe = float(m.get("sharpe", 0.0))
            out[k] = max(0.0, sharpe)
        return out

    # ----------------------
    # Governors / penalties
    # ----------------------
    def _apply_corr_governor(
        self,
        raw: Mapping[str, float],
        corr: Mapping[Tuple[str, str], float],
        *,
        cap: float,
        strength: float,
    ) -> Dict[str, float]:
        ks = list(raw.keys())
        out = dict(raw)
        for i, ki in enumerate(ks):
            for j in range(i + 1, len(ks)):
                kj = ks[j]
                c = float(corr.get((ki, kj), corr.get((kj, ki), 0.0)))
                if c > cap:
                    damp = 1.0 - strength * (c - cap) / max(1e-9, 1 - cap)
                    out[ki] *= max(0.0, min(1.0, damp))
                    out[kj] *= max(0.0, min(1.0, damp))
        return out

    def _apply_turnover_penalty(
        self, prev: Mapping[str, float], new: Mapping[str, float], *, lam: float
    ) -> Dict[str, float]:
        out = {}
        for k, w in new.items():
            p = float(prev.get(k, 0.0))
            out[k] = max(0.0, w - lam * abs(w - p))
        return out

    # ----------------------
    # Utils
    # ----------------------
    @staticmethod
    def _clip(raw: Mapping[str, float], lo: float, hi: float) -> Dict[str, float]:
        return {k: min(hi, max(lo, float(v))) for k, v in raw.items()}

    @staticmethod
    def _normalize(raw: Mapping[str, float]) -> Dict[str, float]:
        s = float(sum(max(0.0, v) for v in raw.values()))
        if s <= 0.0:
            n = len(raw) or 1
            eq = 1.0 / n
            return {k: eq for k in raw.keys()}
        return {k: max(0.0, v) / s for k, v in raw.items()}
