from alpha_factory.ev_exit import synth_fit_ev_policy, write_ev_policy, EVExitPlanner


def test_ev_exit_roundtrip(tmp_path):
    # fit synthetic "best" exit policy
    pol = synth_fit_ev_policy()
    assert pol.expected_value > 0.0

    out_dir = tmp_path / "ev"
    out_dir.mkdir()

    latest_path = write_ev_policy(out_dir, pol)
    assert latest_path.exists()

    planner = EVExitPlanner.load_latest(out_dir)
    plan = planner.propose_exit_plan(features={"foo": 1.0}, symbol="EURUSD")

    assert plan["tp_pips"] == pol.tp_pips
    assert plan["sl_pips"] == pol.sl_pips
    assert plan["expected_value"] == pol.expected_value
    assert "time_stop_bars" in plan
