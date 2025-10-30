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
from alpha_factory.cost_model import CostModel


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

    from alpha_factory.cost_model import CostModel

    def decide_for_trade(
        self,
        feature_row: Dict[str, float],
        base_size: float,
        risk_cap_mult: float,
        symbol: str = "EURUSD",
    ) -> AllocationDecision:
        """
        feature_row: live per-trade features (for ConformalGate).
        base_size: nominal (1.0 == 100% intended size).
        risk_cap_mult: Risk Governor cap (0..1).
        symbol: instrument we're about to trade (for cost model lookup).
        """

        # 1. Conformal filter
        gate = ConformalGate.load_latest(self.conformal_dir)
        conf = gate.score_live_trade(feature_row)
        conf_decision = str(conf.get("decision", "ABSTAIN"))

        if conf_decision != "ACCEPT":
            return AllocationDecision(
                accept=False,
                reasons=["conformal_block"],
                conformal_decision=conf_decision,
                hazard=False,
                base_size=base_size,
                final_size=0.0,
            )

        # 2. Regime hazard
        haz_state = RegimeHazard.load_latest(self.hazard_dir)
        hazard_on = bool(haz_state.hazard)

        sized = float(base_size)

        if hazard_on:
            sized = min(sized, base_size * self.hazard_throttle)

        # 3. Risk Governor cap
        sized = sized * float(risk_cap_mult)

        # 4. COST MODEL (Phase 9)
        cost_dir = self.repo_root / "artifacts" / "cost"
        cm = CostModel.load_latest(cost_dir)
        cost_mult = cm.get_multiplier_for_trade(symbol=symbol, context=None)

        if cost_mult <= 0.0:
            # execution too expensive / liquidity dead -> full block
            return AllocationDecision(
                accept=False,
                reasons=[
                    "conformal_accept",
                    "hazard_throttle" if hazard_on else "no_hazard",
                    "risk_cap" if risk_cap_mult < 1.0 else "risk_ok",
                    "cost_block",
                ],
                conformal_decision=conf_decision,
                hazard=hazard_on,
                base_size=base_size,
                final_size=0.0,
            )

        sized = sized * cost_mult

        # cleanup
        if sized < 0.0:
            sized = 0.0

        accept_flag = sized > 0.0 and risk_cap_mult > 0.0 and cost_mult > 0.0

        reasons = []
        reasons.append("conformal_accept")
        reasons.append("hazard_throttle" if hazard_on else "no_hazard")
        reasons.append("risk_cap" if risk_cap_mult < 1.0 else "risk_ok")
        if cost_mult < 1.0:
            reasons.append("cost_throttle")

        return AllocationDecision(
            accept=accept_flag,
            reasons=reasons,
            conformal_decision=conf_decision,
            hazard=hazard_on,
            base_size=base_size,
            final_size=sized,
        )
