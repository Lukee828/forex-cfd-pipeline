# tests/alpha_factory/test_live_bridge_phase12.py
from __future__ import annotations

from pathlib import Path
import json

from alpha_factory.live_guard_config import (
    save_config,
    LiveConfig,
    mark_breach,
)
from alpha_factory.bridge_contract import (
    guard_pretrade_allowed,
    tradeplan_to_contract,
    append_intent,
    write_next_order,
)
from alpha_factory.live_reconcile import build_execution_report


def _fake_tradeplan_dict() -> dict:
    """
    This mimics ExecutionPlanner.TradePlan.to_dict() output.
    We shortcut here instead of importing ExecutionPlanner to keep the test fast.
    """
    return {
        "accept": True,
        "final_size": 0.35,
        "reasons": [
            "conformal_accept",
            "risk_ok",
            "hazard_ok",
            "cost_ok",
            "ev_positive",
        ],
        "tp_pips": 20.0,
        "sl_pips": 10.0,
        "time_stop_bars": 50,
        "expected_value": 0.007,
        "meta": {
            "symbol": "EURUSD",
            "hazard": False,
            "ev_note": "best-historical-bucket",
            "conformal_decision": "ACCEPT",
        },
    }


def test_pretrade_guard_blocks_if_disabled(tmp_path: Path):
    # write config with live_enabled = False
    cfg = LiveConfig(
        live_enabled=False,
        max_spread_pips=2.0,
        max_slippage_pips=1.5,
        max_latency_sec=2.5,
    )
    save_config(tmp_path, cfg)

    # should raise because live is disabled
    raised = False
    try:
        guard_pretrade_allowed(
            repo_root=tmp_path,
            spread_pips=0.5,
            last_tick_age_sec=0.2,
        )
    except RuntimeError as ex:
        raised = True
        assert "LIVE_DISABLED" in str(ex)

    assert raised is True

    # re-enable live and make sure we're allowed
    cfg2 = LiveConfig(
        live_enabled=True,
        max_spread_pips=2.0,
        max_slippage_pips=1.5,
        max_latency_sec=2.5,
    )
    save_config(tmp_path, cfg2)

    # now should NOT raise
    guard_pretrade_allowed(
        repo_root=tmp_path,
        spread_pips=0.5,
        last_tick_age_sec=0.2,
    )

    # mark breach file to simulate kill switch after slippage violation
    mark_breach(tmp_path, "slippage too high")

    # now it SHOULD raise again
    raised2 = False
    try:
        guard_pretrade_allowed(
            repo_root=tmp_path,
            spread_pips=0.5,
            last_tick_age_sec=0.2,
        )
    except RuntimeError as ex:
        raised2 = True
        assert "BREACH" in str(ex)

    assert raised2 is True


def test_ticket_and_journal_flow(tmp_path: Path):
    """
    Dry-run version of the production LiveGuard happy path:
    - guard allows trade
    - planner (here faked) produces tradeplan dict
    - convert to contract
    - log INTENT
    - write next_order.json
    - confirm artefacts are sane
    - call build_execution_report() with no fills yet
    """

    # enable live in config, no breach
    cfg_live = LiveConfig(
        live_enabled=True,
        max_spread_pips=5.0,  # loose for the test
        max_slippage_pips=10.0,
        max_latency_sec=10.0,
    )
    save_config(tmp_path, cfg_live)

    # guard should pass (no exception)
    guard_pretrade_allowed(
        repo_root=tmp_path,
        spread_pips=1.0,
        last_tick_age_sec=0.1,
    )

    # fake planner output -> contract
    tp = _fake_tradeplan_dict()
    contract = tradeplan_to_contract(tp)

    assert contract["accept"] is True
    assert contract["size"] == 0.35
    assert contract["symbol"] == "EURUSD"
    assert "ticket_nonce" in contract and contract["ticket_nonce"]
    assert contract["reasons"]

    # write INTENT to journal
    append_intent(tmp_path, contract)

    # write next_order.json ticket for EA
    ticket_path = write_next_order(tmp_path, contract)
    assert ticket_path.exists()

    raw_ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert raw_ticket["symbol"] == "EURUSD"
    assert raw_ticket["size"] == 0.35

    # journal.ndjson should now have exactly one INTENT line
    journal_path = tmp_path / "artifacts" / "live" / "journal.ndjson"
    assert journal_path.exists()
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    j0 = json.loads(lines[0])
    assert j0["type"] == "INTENT"
    assert j0["contract"]["size"] == 0.35

    # build_execution_report() with no FILL yet should still
    # produce a well-formed structure and safe defaults
    rep = build_execution_report(tmp_path)

    # new shape (Phase 14+):
    # {
    #   "pairs": [...],
    #   "summary": {
    #       "fill_ratio": float,
    #       "avg_slippage_pips": Optional[float],
    #       "avg_latency_sec": Optional[float],
    #       "n_fills": int,
    #       ...
    #   }
    # }
    assert "summary" in rep
    summary = rep["summary"]

    assert "fill_ratio" in summary
    assert "avg_slippage_pips" in summary
    assert "avg_latency_sec" in summary
    assert "n_fills" in summary

    # with 0 fills, contract hasn't been executed yet
    # we expect 0 fill ratio, 0 fills, and None for timing/slippage avgs
    assert summary["n_fills"] == 0
    assert summary["fill_ratio"] == 0.0
    assert summary["avg_slippage_pips"] is None
    assert summary["avg_latency_sec"] is None
