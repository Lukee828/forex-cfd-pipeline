from pathlib import Path
import json
from alpha_factory.bridge_contract import (
    tradeplan_to_contract,
    append_intent,
    record_fill_from_ea,
)
from alpha_factory.live_reconcile import build_execution_report


def _fake_tradeplan(symbol: str, size: float) -> dict:
    """
    Minimal TradePlan-style dict for reconciliation tests.
    """
    return {
        "accept": True,
        "final_size": size,
        "reasons": ["ok_for_test"],
        "tp_pips": 20.0,
        "sl_pips": 10.0,
        "time_stop_bars": 50,
        "expected_value": 0.01,
        "meta": {
            "symbol": symbol,
            "hazard": False,
            "ev_note": "unit-test",
            "conformal_decision": "ACCEPT",
        },
    }


def test_reconcile_builds_report_from_intent_and_fill(tmp_path: Path):
    """
    Phase 14/15 reconciliation loop:
    1. Planner makes a TradePlan.
    2. We convert to broker-facing contract.
    3. append_intent() logs INTENT to journal.ndjson.
    4. record_fill_from_ea() logs FILL to journal.ndjson.
    5. build_execution_report() outputs pairs[] and summary{}.
    """

    # Arrange directories like runtime expects
    live_dir = tmp_path / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    # Fake planner output and convert to contract
    tp = _fake_tradeplan(symbol="EURUSD", size=0.25)
    contract = tradeplan_to_contract(tp)

    # 1) INTENT: user wants to open this trade
    append_intent(tmp_path, contract)

    # 2) Simulate broker fill (what Bridge-Fill.ps1 will actually pass us now)
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

    # journal.ndjson should now contain INTENT and FILL
    journal_path = live_dir / "journal.ndjson"
    assert journal_path.exists()

    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    j_intent = json.loads(lines[0])
    j_fill = json.loads(lines[1])

    # --- INTENT checks
    assert j_intent["type"] == "INTENT"
    assert "contract" in j_intent
    assert j_intent["contract"]["ticket_nonce"] == contract["ticket_nonce"]
    assert j_intent["contract"]["size"] == 0.25

    # --- FILL checks
    assert j_fill["type"] == "FILL"
    assert "fill" in j_fill
    f = j_fill["fill"]

    # Nonce link for reconciliation
    assert f["ticket_nonce"] == contract["ticket_nonce"]

    # Execution details
    assert f["symbol"] == "EURUSD"
    assert f["side"] in ("BUY", "SELL")
    assert f["size_exec"] == 0.25
    assert f["price_exec"] == 1.2345
    assert f["slippage_pips"] == 0.3
    assert f["latency_sec"] == 0.2
    assert str(f["ticket_id"]) == "MT5-555"

    # 3) Reconcile INTENT vs FILL into metrics/report
    rep = build_execution_report(tmp_path)

    # The report should have the expected high-level structure
    assert isinstance(rep, dict)
    assert "pairs" in rep
    assert "summary" in rep

    pairs = rep["pairs"]
    summary = rep["summary"]

    # pairs should be a list (possibly length 1 when one fill exists)
    assert isinstance(pairs, list)
    assert len(pairs) >= 1

    # summary should expose high-level execution stats keys,
    # even if the exact numeric rollups evolve over time.
    for key in [
        "n_fills",
        "fill_ratio",
        "avg_slippage_pips",
        "avg_latency_sec",
    ]:
        assert key in summary
