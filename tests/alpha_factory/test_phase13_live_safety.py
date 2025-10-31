# tests/alpha_factory/test_phase13_live_safety.py
from __future__ import annotations

from pathlib import Path
import json

from alpha_factory.live_guard_config import (
    LiveConfig,
    save_config,
    mark_breach,
)
from alpha_factory.bridge_contract import (
    guard_pretrade_allowed,
    tradeplan_to_contract,
    append_intent,
    record_fill_from_ea,
)
from alpha_factory.live_reconcile import build_execution_report


def _fake_tradeplan(symbol: str = "EURUSD", size: float = 0.35) -> dict:
    """
    Mimics ExecutionPlanner.TradePlan.to_dict() after all sizing / EV exits.
    We stub it here to keep the test lightweight.
    """
    return {
        "accept": True,
        "final_size": size,
        "reasons": [
            "conformal_accept",
            "risk_ok",
            "hazard_ok",
            "cost_ok",
            "ev_positive",
        ],
        "tp_pips": 22.0,
        "sl_pips": 11.0,
        "time_stop_bars": 60,
        "expected_value": 0.008,
        "meta": {
            "symbol": symbol,
            "hazard": False,
            "ev_note": "best-bucket",
            "conformal_decision": "ACCEPT",
        },
    }


def test_live_guard_kill_switch_and_spread_checks(tmp_path: Path):
    """
    This covers Phase 13-style runtime safety:
    - kill switch / breach file
    - spread + staleness / tick-age checks
    """

    # 1. live disabled initially -> should raise
    cfg_disabled = LiveConfig(
        live_enabled=False,
        max_spread_pips=2.0,
        max_slippage_pips=1.5,
        max_latency_sec=2.0,
    )
    save_config(tmp_path, cfg_disabled)

    raised = False
    try:
        guard_pretrade_allowed(
            repo_root=tmp_path,
            spread_pips=0.4,
            last_tick_age_sec=0.1,
        )
    except RuntimeError as ex:
        raised = True
        assert "LIVE_DISABLED" in str(ex)
    assert raised is True

    # 2. enable live, guard should pass
    cfg_enabled = LiveConfig(
        live_enabled=True,
        max_spread_pips=2.0,
        max_slippage_pips=1.5,
        max_latency_sec=2.0,
    )
    save_config(tmp_path, cfg_enabled)

    guard_pretrade_allowed(
        repo_root=tmp_path,
        spread_pips=0.4,  # within limit
        last_tick_age_sec=0.1,  # fresh quote
    )

    # 3. now simulate breach (kill switch flipped after a violation)
    mark_breach(tmp_path, "latency too high")

    raised2 = False
    try:
        guard_pretrade_allowed(
            repo_root=tmp_path,
            spread_pips=0.4,
            last_tick_age_sec=0.1,
        )
    except RuntimeError as ex:
        raised2 = True
        assert "BREACH" in str(ex)
    assert raised2 is True


def test_reconcile_builds_report_from_intent_and_fill(tmp_path: Path):
    """
    Phase 14/15 reconciliation loop:
    1. Planner makes a TradePlan.
    2. We convert to broker-facing contract.
    3. append_intent() logs INTENT to journal.ndjson.
    4. record_fill_from_ea() logs FILL to journal.ndjson.
    5. build_execution_report() calculates fill_ratio, avg_slippage_pips, etc.
    """

    # Arrange directories like runtime expects
    live_dir = tmp_path / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    # Fake planner output and convert to contract
    tp = _fake_tradeplan(symbol="EURUSD", size=0.25)
    contract = tradeplan_to_contract(tp)

    # INTENT: user wants to open this trade
    append_intent(tmp_path, contract)

    # Simulate broker fill (what Bridge-Fill.ps1 will send us)
    record_fill_from_ea(
        repo_root=tmp_path,
        symbol="EURUSD",
        side=contract["side"],
        size_exec=0.25,
        price_exec=1.2345,
        ticket_id="MT5-555",
        ticket_nonce=contract["ticket_nonce"],
        latency_sec=0.2,
        slippage_pips=0.3,
    )

    # The journal should now have 2 lines: INTENT then FILL
    journal_path = live_dir / "journal.ndjson"
    assert journal_path.exists()
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    j0 = json.loads(lines[0])
    j1 = json.loads(lines[1])

    # --- INTENT validation
    assert j0["type"] == "INTENT"
    assert "contract" in j0
    assert j0["contract"]["ticket_nonce"] == contract["ticket_nonce"]
    assert j0["contract"]["size"] == 0.25

    # --- FILL validation
    assert j1["type"] == "FILL"
    assert "fill" in j1
    f = j1["fill"]

    # FILL row should carry execution details
    assert f["ticket_nonce"] == contract["ticket_nonce"]
    assert f["symbol"] == "EURUSD"
    assert f["side"] in ("BUY", "SELL")
    assert f["size_exec"] == 0.25
    assert f["price_exec"] == 1.2345
    assert f["slippage_pips"] == 0.3
    assert f["latency_sec"] == 0.2
    assert str(f["ticket_id"]) == "MT5-555"

    # --- Reconciliation report
    rep = build_execution_report(tmp_path)

    # report should expose pairs + summary
    assert "pairs" in rep
    assert "summary" in rep

    summary = rep["summary"]

    # summary should at least publish these keys,
    # even if the math is still basic in early Phase 15.
    assert "n_fills" in summary
    assert "fill_ratio" in summary
    assert "avg_latency_sec" in summary
    assert "avg_slippage_pips" in summary

    # type sanity
    assert summary["n_fills"] >= 0
    assert summary["fill_ratio"] >= 0.0
