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

    def allocate(
        self,
        metrics: Metrics,
        *,
        prev_weights: Mapping[str, float] | None = None,
        corr: Mapping[tuple[str, str], float] | None = None,
        smooth: float = 0.10,
        corr_penalty: float = 0.25,
    ) -> Dict[str, float]:
        """
        Allocate across sleeves.

        Args:
            metrics: per-sleeve metrics.
            prev_weights: optional previous weights to blend toward (stability).
            corr: optional pairwise correlations {(a,b): rho, ...} symmetric.
            smooth: blend strength toward prev_weights in [0..1].
            corr_penalty: how strongly to penalize correlation exposure.

        Returns:
            Dict[str, float]: normalized weights summing to ~1.0.
        """
        if not metrics:
            return {}

        mode = (self.cfg.mode or "ewma").lower()
        try:
            if mode == "equal":
                w = self._equal(metrics)
            elif mode == "bayes":
                w = self._bayes(metrics)
            else:
                w = self._ewma(metrics)
        except Exception:
            w = self._equal(metrics)

        # --- Optional smoothing toward previous weights
        if prev_weights and smooth > 0.0:
            # ensure same keyset; missing keys -> 0
            keys = set(w) | set(prev_weights)
            prev = {k: max(float(prev_weights.get(k, 0.0)), 0.0) for k in keys}
            prev = self._normalize(prev)
            w = {k: (1.0 - smooth) * float(w.get(k, 0.0)) + smooth * prev.get(k, 0.0) for k in keys}
            w = self._normalize(w)

        # --- Optional correlation penalty (reduce exposure where peers highly correlated)
        if corr and corr_penalty > 0.0 and w:
            keys = list(w.keys())
            # aggregate correlation pressure per name as sum_j rho(i,j)*w_j (rho<0 ignored)
            press = {k: 0.0 for k in keys}
            for (a, b), rho in corr.items():
                if a in press and b in press and rho is not None and rho > 0.0:
                    press[a] += rho * w.get(b, 0.0)
                    press[b] += rho * w.get(a, 0.0)
            # shrink by (1 - corr_penalty * pressure), floor at 0
            shrunk = {k: max(w[k] * (1.0 - corr_penalty * press[k]), 0.0) for k in keys}
            w = self._normalize(shrunk)

        return self._normalize(w)
