from __future__ import annotations

from pathlib import Path
import json

from alpha_factory.bridge_contract import (
    build_live_safe_contract,
    write_next_order,
    append_trade_intent,
    append_trade_fill,
    _write_json,
)


def _write_cfg(tmp: Path, live_enabled: bool = False):
    """Helper: write a Phase 13-style live_guard_config.json."""
    cfg_path = tmp / "artifacts" / "live" / "live_guard_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        cfg_path,
        {
            "live_enabled": live_enabled,
            "max_spread_pips": 2.5,
            "max_age_sec": 5,
            "min_size": 0.05,
            "max_size": 1.00,
            "dup_window_sec": 30,
        },
    )


def test_liveguard_happy_path_and_ticket_write(tmp_path: Path):
    """
    Full dry-run loop:
    - synthesize TradePlan dict (what ExecutionPlanner would output)
    - build_live_safe_contract() applies safety rules + dedup
    - write_next_order() writes the EA ticket
    - append_trade_intent() journals INTENT
    - append_trade_fill() journals FILL
    """

    # prepare config (this time we ENABLE live so contract can pass)
    _write_cfg(tmp_path, live_enabled=True)

    # fake TradePlan ("what planner.build_trade_plan(...).to_dict()" returns)
    tp = {
        "accept": True,
        "final_size": 0.35,
        "tp_pips": 25.0,
        "sl_pips": 12.0,
        "time_stop_bars": 80,
        "expected_value": 0.011,
        "reasons": ["conformal_ok", "hazard_ok", "risk_cap_ok"],
        "meta": {
            "symbol": "EURUSD",
            "hazard": False,
            "ev_note": "synthetic-best",
            "conformal_decision": "ACCEPT",
        },
    }

    # runtime context we'd normally get from MT5 + model recency
    market_spread_pips = 1.2  # inside limit
    model_age_sec = 1.0  # fresh

    # Phase 13 safe contract build
    contract = build_live_safe_contract(
        repo_root=tmp_path,
        tp_dict=tp,
        market_spread_pips=market_spread_pips,
        model_age_sec=model_age_sec,
    )

    # contract should still be allowed
    assert contract["symbol"] == "EURUSD"
    assert contract["size"] == 0.35
    assert contract["accept"] is True

    # write EA ticket
    ticket_path = write_next_order(tmp_path, contract)
    assert ticket_path.exists()
    saved = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert saved["symbol"] == "EURUSD"
    assert saved["accept"] is True

    # INTENT journal line
    journal_path = tmp_path / "artifacts" / "live" / "journal.ndjson"
    append_trade_intent(journal_path, contract)
    text_after_intent = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(text_after_intent) == 1
    assert '"event": "INTENT"' in text_after_intent[0]
    assert '"EURUSD"' in text_after_intent[0]

    # FILL journal line (pretend MT5 executed)
    append_trade_fill(
        journal_path=journal_path,
        ticket_id="MT5-55555",
        symbol="EURUSD",
        price_fill=1.08321,
        filled_size=0.35,
    )
    text_all = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(text_all) == 2
    assert '"event": "FILL"' in text_all[1]
    assert '"ticket_id": "MT5-55555"' in text_all[1]

    # sanity: timestamps look ISO-ish
    # just check we added something that looks like UTC time
    assert "ts_utc" in text_all[0]
    assert "ts_utc" in text_all[1]

    # sanity: we can parse the INTENT line back to dict
    first_evt = json.loads(text_all[0])
    assert first_evt["event"] == "INTENT"
    assert first_evt["contract"]["symbol"] == "EURUSD"

    # sanity: we can parse the FILL line back
    second_evt = json.loads(text_all[1])
    assert second_evt["event"] == "FILL"
    assert second_evt["ticket_id"] == "MT5-55555"
    assert second_evt["symbol"] == "EURUSD"
    assert second_evt["filled_size"] == 0.35

    # no exception so far => we're good for dry-run
    # also ensure we didn't write anything outside tmp_path
    assert str(tmp_path) in str(ticket_path)
    assert str(tmp_path) in str(journal_path)
