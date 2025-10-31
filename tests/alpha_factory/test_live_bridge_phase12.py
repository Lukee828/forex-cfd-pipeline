from __future__ import annotations

from pathlib import Path
import json
from alpha_factory.bridge_contract import (
    tradeplan_to_contract,
    append_trade_intent,
    record_fill,
)


def test_intent_and_fill_journaling(tmp_path: Path):
    repo_root = tmp_path

    # pretend TradePlan -> contract
    tp = {
        "accept": True,
        "symbol": "EURUSD",
        "side": "BUY",
        "size": 0.5,
        "reasons": ["ok"],
        "exits": {"tp": 1.0720, "sl": 1.0690},
    }
    contract = tradeplan_to_contract(tp)

    # journal INTENT
    trades_path = append_trade_intent(repo_root, contract)
    txt_trades = trades_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(txt_trades) >= 1
    rec_intent = json.loads(txt_trades[-1])
    assert rec_intent["type"] == "INTENT"
    assert rec_intent["contract"]["symbol"] == "EURUSD"

    # fake EA fill
    fill = {
        "timestamp_utc": "2025-10-31T12:00:00Z",
        "symbol": "EURUSD",
        "side": "BUY",
        "size": 0.48,
        "fill_price": 1.07195,
        "ticket_id": 1234567,
        "status": "FILLED",
        "slippage_pips": 0.3,
    }

    fills_path = record_fill(repo_root, fill)
    txt_fills = fills_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(txt_fills) >= 1
    rec_fill = json.loads(txt_fills[-1])
    assert rec_fill["type"] == "FILL"
    assert rec_fill["fill"]["ticket_id"] == 1234567
    assert rec_fill["fill"]["status"] == "FILLED"
