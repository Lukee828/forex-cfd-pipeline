from alpha_factory.execution_planner import ExecutionPlanner, TradePlan
from alpha_factory.alloc_decider import AllocationDecider
from alpha_factory.ev_exit import EVExitPlanner


def test_execution_planner_builds_trade_plan(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "artifacts" / "ev").mkdir(parents=True)
    (repo_root / "artifacts" / "conformal").mkdir(parents=True)
    (repo_root / "artifacts" / "regime").mkdir(parents=True)
    (repo_root / "artifacts" / "cost").mkdir(parents=True)

    # stub AllocationDecider.decide_for_trade
    class DummyAlloc:
        accept = True
        final_size = 0.42
        reasons = ["conformal_accept", "risk_ok", "cost_throttle"]
        conformal_decision = "ACCEPT"
        hazard = False

    def fake_decide_for_trade(self, feature_row, base_size, risk_cap_mult, symbol="EURUSD"):
        return DummyAlloc()

    monkeypatch.setattr(AllocationDecider, "decide_for_trade", fake_decide_for_trade)

    # stub EVExitPlanner.load_latest
    class DummyPlanner:
        def propose_exit_plan(self, features, symbol="EURUSD"):
            return {
                "tp_pips": 25.0,
                "sl_pips": 12.0,
                "time_stop_bars": 80,
                "expected_value": 0.011,
                "note": "synthetic-best",
                "as_of": "2025-10-30T12:00:00Z",
                "symbol": symbol,
            }

    def fake_load_latest_ev(dirpath):
        return DummyPlanner()

    monkeypatch.setattr(EVExitPlanner, "load_latest", staticmethod(fake_load_latest_ev))

    planner = ExecutionPlanner(repo_root=repo_root)
    tp = planner.build_trade_plan(
        feature_row={"dummy": 1.0},
        base_size=1.0,
        risk_cap_mult=1.0,
        symbol="EURUSD",
    )

    assert isinstance(tp, TradePlan)
    assert tp.accept is True
    assert tp.final_size == 0.42
    assert tp.tp_pips == 25.0
    assert tp.sl_pips == 12.0
    assert tp.time_stop_bars == 80
    assert tp.expected_value == 0.011
    assert "conformal_accept" in tp.reasons
    assert tp.meta["ev_note"] == "synthetic-best"
    assert tp.meta["conformal_decision"] == "ACCEPT"
