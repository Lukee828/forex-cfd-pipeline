from __future__ import annotations

from pathlib import Path
from alpha_factory.bridge_contract import tradeplan_to_contract, write_next_order


def test_bridge_contract_writes_ticket_and_journal(tmp_path: Path):
    # Fake trade_plan dict (mimics ExecutionPlanner.TradePlan.to_dict())
    fake_trade_plan = {
        "accept": True,
        "final_size": 0.42,
        "reasons": [
            "conformal_accept",
            "risk_ok",
            "cost_throttle",
            "ev_positive",
        ],
        "tp_pips": 25.0,
        "sl_pips": 12.0,
        "time_stop_bars": 80,
        "expected_value": 0.011,
        "meta": {
            "symbol": "EURUSD",
            "hazard": False,
            "ev_note": "synthetic-best",
            "conformal_decision": "ACCEPT",
        },
    }

    contract = tradeplan_to_contract(fake_trade_plan)

    # contract sanity
    assert contract["symbol"] == "EURUSD"
    assert contract["side"] == "BUY"
    assert contract["size"] == 0.42
    assert contract["tp_pips"] == 25.0
    assert contract["accept"] is True
    assert "timestamp_utc" in contract

    out_path = write_next_order(tmp_path, contract)

    # next_order.json exists and has expected fields
    assert out_path.exists()
    data = out_path.read_text(encoding="utf-8")
    assert '"EURUSD"' in data
    assert '"tp_pips": 25.0' in data
    assert '"size": 0.42' in data

    # journal file exists and got one line
    journal_dir = tmp_path / "artifacts" / "journal"
    journal_files = list(journal_dir.glob("trades_*.jsonl"))
    assert len(journal_files) == 1

    journal_text = journal_files[0].read_text(encoding="utf-8").strip()
    # should contain a JSON per line, same contract
    assert '"EURUSD"' in journal_text
    assert '"size": 0.42' in journal_text
    assert '"tp_pips": 25.0' in journal_text
