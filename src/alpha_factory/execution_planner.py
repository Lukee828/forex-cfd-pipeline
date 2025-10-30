"""
alpha_factory.execution_planner
Phase 10 glue.

Takes AllocationDecider (Phase 8/9) + EVExitPlanner (Phase 10)
and returns a final executable trade plan:
- should we trade?
- size?
- exit policy?
- audit trail (reasons, EV, regime info, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
import pathlib

from alpha_factory.alloc_decider import AllocationDecider
from alpha_factory.ev_exit import EVExitPlanner


@dataclass
class TradePlan:
    accept: bool
    final_size: float
    reasons: list[str]
    tp_pips: float
    sl_pips: float
    time_stop_bars: int
    expected_value: float
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutionPlanner:
    def __init__(self, repo_root: str | pathlib.Path):
        self.repo_root = pathlib.Path(repo_root)
        self.decider = AllocationDecider(repo_root=self.repo_root)
        self.ev_dir = self.repo_root / "artifacts" / "ev"

    def build_trade_plan(
        self,
        feature_row: Dict[str, float],
        base_size: float,
        risk_cap_mult: float,
        symbol: str = "EURUSD",
    ) -> TradePlan:
        """
        1. Ask AllocationDecider for size/accept + reasons.
        2. Load EVExitPlanner.latest and propose exit params.
        3. Bundle one coherent plan.
        """

        alloc = self.decider.decide_for_trade(
            feature_row=feature_row,
            base_size=base_size,
            risk_cap_mult=risk_cap_mult,
            symbol=symbol,
        )

        # if alloc.reject => we still attach exit info, but size=0
        planner = EVExitPlanner.load_latest(self.ev_dir)
        exit_plan = planner.propose_exit_plan(
            features=feature_row,
            symbol=symbol,
        )

        return TradePlan(
            accept=alloc.accept,
            final_size=alloc.final_size,
            reasons=alloc.reasons,
            tp_pips=exit_plan["tp_pips"],
            sl_pips=exit_plan["sl_pips"],
            time_stop_bars=exit_plan["time_stop_bars"],
            expected_value=exit_plan["expected_value"],
            meta={
                "symbol": symbol,
                "conformal_decision": alloc.conformal_decision,
                "hazard": alloc.hazard,
                "ev_note": exit_plan["note"],
                "as_of_ev": exit_plan["as_of"],
            },
        )
