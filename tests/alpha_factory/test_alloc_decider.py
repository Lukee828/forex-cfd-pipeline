from __future__ import annotations
from alpha_factory.alloc_decider import AllocationDecider
from alpha_factory.conformal_gate import ConformalGate
from alpha_factory.regime_hazard import RegimeHazard, RegimeHazardState
from alpha_factory.cost_model import CostModel


def test_allocator_merges_conformal_hazard_and_risk(monkeypatch, tmp_path):
    repo_root = tmp_path
    # create the dirs the decider expects
    (repo_root / "artifacts" / "conformal").mkdir(parents=True)
    (repo_root / "artifacts" / "regime").mkdir(parents=True)
    (repo_root / "artifacts" / "cost").mkdir(parents=True)

    # --- stub ConformalGate.load_latest
    class DummyGate:
        def score_live_trade(self, row):
            return {"decision": "ACCEPT", "p_win": 0.73}

    def fake_load_latest_conformal(_path):
        return DummyGate()

    monkeypatch.setattr(ConformalGate, "load_latest", staticmethod(fake_load_latest_conformal))

    # --- stub RegimeHazard.load_latest
    def fake_load_latest_hazard(_path):
        return RegimeHazardState(
            as_of="2025-10-30T11:11:11Z",
            hazard=True,
            reason="vol_spike",
            score=5.0,
            cooldown_bars=30,
        )

    monkeypatch.setattr(RegimeHazard, "load_latest", staticmethod(fake_load_latest_hazard))

    # --- stub CostModel.load_latest
    class DummyCostModel:
        def get_multiplier_for_trade(self, symbol: str, context=None):
            # pretend liquidity is THIN -> multiplier 0.6
            return 0.6

    def fake_load_latest_cost(_path):
        return DummyCostModel()

    monkeypatch.setattr(CostModel, "load_latest", staticmethod(fake_load_latest_cost))

    # build decider
    decider = AllocationDecider(
        repo_root=repo_root,
        hazard_throttle=0.35,  # if hazard, max 35% of base
    )

    # candidate trade request
    base_size = 1.0
    risk_cap_mult = 0.5  # Risk Governor says "half size at most"
    feature_row = {"dummy": 1.23}

    decision = decider.decide_for_trade(
        feature_row=feature_row,
        base_size=base_size,
        risk_cap_mult=risk_cap_mult,
        symbol="EURUSD",
    )

    # expectations:
    # conformal ACCEPT -> allowed
    # hazard ON -> throttle to 0.35 * base_size = 0.35
    # risk cap 0.5 -> 0.35 * 0.5 = 0.175
    # cost multiplier 0.6 -> 0.175 * 0.6 = 0.105
    assert decision.accept is True
    assert abs(decision.final_size - 0.105) < 1e-9

    # we should record all the right "reasons"
    assert "conformal_accept" in decision.reasons
    assert "hazard_throttle" in decision.reasons or "no_hazard" in decision.reasons
    assert "risk_cap" in decision.reasons or "risk_ok" in decision.reasons
    # Because cost_mult < 1.0 we expect throttling
    assert "cost_throttle" in decision.reasons

    # sanity on metadata
    assert decision.hazard is True
    assert decision.conformal_decision == "ACCEPT"
