from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Mapping

Metrics = Mapping[str, Mapping[str, float]]


@dataclass
class AllocatorConfig:
    mode: str = "ewma"  # "equal" | "ewma" | "bayes"
    sharpe_weight: float = 0.75
    dd_weight: float = 0.25
    min_weight: float = 0.0
    max_weight: float = 1.0
    eps: float = 1e-9


class MetaAllocator:
    def __init__(self, cfg: AllocatorConfig | None = None):
        self.cfg = cfg or AllocatorConfig()

    def _score(self, m: Mapping[str, float]) -> float:
        # Higher Sharpe, lower DD -> higher score
        s = float(m.get("sharpe", 0.0))
        dd = float(m.get("dd", 0.0))
        inv_dd = 1.0 / (dd + self.cfg.eps)
        return self.cfg.sharpe_weight * s + self.cfg.dd_weight * inv_dd

    def _normalize(self, raw: Dict[str, float]) -> Dict[str, float]:
        # clip + renormalize
        clipped = {k: min(max(v, self.cfg.min_weight), self.cfg.max_weight) for k, v in raw.items()}
        tot = sum(max(v, 0.0) for v in clipped.values())
        if tot <= self.cfg.eps:
            n = len(clipped) or 1
            return {k: 1.0 / n for k in clipped}
        return {k: v / tot for k, v in clipped.items()}

    def _equal(self, metrics: Metrics) -> Dict[str, float]:
        keys = list(metrics.keys())
        if not keys:
            return {}
        w = 1.0 / len(keys)
        return {k: w for k in keys}

    def _ewma(self, metrics: Metrics) -> Dict[str, float]:
        # Single-shot scoring; “ewma” name reserved for later time decay extension
        raw = {k: max(self._score(v), 0.0) for k, v in metrics.items()}
        return self._normalize(raw)

    def _bayes(self, metrics: Metrics) -> Dict[str, float]:
        # Bayes-lite: positive evidence ~ Sharpe+, negative ~ DD (as pseudo counts)
        raw: Dict[str, float] = {}
        for k, v in metrics.items():
            s = max(float(v.get("sharpe", 0.0)), 0.0)
            dd = max(float(v.get("dd", 0.0)), 0.0)
            alpha = 1.0 + s  # prior + “success”
            beta = 1.0 + 10.0 * dd  # prior + “failures” scaled by DD
            p = alpha / (alpha + beta)
            raw[k] = max(p, 0.0)
        return self._normalize(raw)

    def allocate(self, metrics: Metrics) -> Dict[str, float]:
        if not metrics:
            return {}
        mode = (self.cfg.mode or "ewma").lower()
        try:
            if mode == "equal":
                out = self._equal(metrics)
            elif mode == "bayes":
                out = self._bayes(metrics)
            else:
                out = self._ewma(metrics)
        except Exception:
            # hard fallback for robustness
            out = self._equal(metrics)
        return self._normalize(out)
