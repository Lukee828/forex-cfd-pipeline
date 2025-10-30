"""
alpha_factory.alloc_decider
Phase 8 (Allocator Integration)

This combines:
- ConformalGate (trade quality)
- RegimeHazard (market regime risk)
- Risk Governor headroom (global risk cap)

It returns a final decision + size multiplier for a candidate trade.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
import pathlib
from alpha_factory.conformal_gate import ConformalGate
from alpha_factory.regime_hazard import RegimeHazard


@dataclass
class AllocationDecision:
    accept: bool
    reasons: list[str]
    conformal_decision: str
    hazard: bool
    base_size: float
    final_size: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AllocationDecider:
    def __init__(
        self,
        repo_root: str | pathlib.Path,
        hazard_dir: str = "artifacts/regime",
        conformal_dir: str = "artifacts/conformal",
        hazard_throttle: float = 0.35,
    ):
        """
        hazard_throttle: if hazard is ON, cap final_size <= base_size * hazard_throttle.
        """
        self.repo_root = pathlib.Path(repo_root)
        self.hazard_dir = self.repo_root / hazard_dir
        self.conformal_dir = self.repo_root / conformal_dir
        self.hazard_throttle = hazard_throttle

    def decide_for_trade(
        self,
        feature_row: Dict[str, float],
        base_size: float,
        risk_cap_mult: float,
    ) -> AllocationDecision:
        """
        feature_row: dict of live features for this trade (what ConformalGate expects)
        base_size: nominal intended position size (e.g. 1.0 == 100%)
        risk_cap_mult: global cap from Risk Governor (0.0-1.0),
                       e.g. 1.0 means full allowed, 0.5 means halve size,
                       0.0 means no more exposure allowed.

        Returns AllocationDecision.
        """

        # 1. Conformal filter (per-trade)
        gate = ConformalGate.load_latest(self.conformal_dir)
        conf = gate.score_live_trade(feature_row)
        conf_decision = str(conf.get("decision", "ABSTAIN"))

        if conf_decision != "ACCEPT":
            # Hard block. Do not size at all.
            return AllocationDecision(
                accept=False,
                reasons=["conformal_block"],
                conformal_decision=conf_decision,
                hazard=False,
                base_size=base_size,
                final_size=0.0,
            )

        # 2. Regime hazard (global environment risk)
        haz_state = RegimeHazard.load_latest(self.hazard_dir)
        hazard_on = bool(haz_state.hazard)

        # Start from base size if conformal was okay
        sized = float(base_size)

        # Apply hazard throttle
        if hazard_on:
            sized = min(sized, base_size * self.hazard_throttle)

        # 3. Apply Risk Governor cap multiplier
        sized = sized * float(risk_cap_mult)

        # Enforce non-negative
        if sized < 0.0:
            sized = 0.0

        accept_flag = sized > 0.0 and risk_cap_mult > 0.0

        reasons = []
        reasons.append("conformal_accept")
        if hazard_on:
            reasons.append("hazard_throttle")
        if risk_cap_mult < 1.0:
            reasons.append("risk_cap")

        return AllocationDecision(
            accept=accept_flag,
            reasons=reasons,
            conformal_decision=conf_decision,
            hazard=hazard_on,
            base_size=base_size,
            final_size=sized,
        )
