from __future__ import annotations

# ruff: noqa: E402

"""alpha_factory.bridge_contract
Phase 11 (Pre-Live Safety)

This module is the "handoff contract" between research brain (Python)
and execution (MT5 BridgeEA).

Responsibilities:
- Convert a TradePlan (from ExecutionPlanner) into a lean broker ticket.
- Write that ticket to artifacts/live/next_order.json for AF_BridgeEA.mq5.
- Append the same ticket to artifacts/journal/trades_YYYYMMDD.jsonl
  so calibration jobs can learn from real trades later.

Nothing here talks to MetaTrader5 directly. This is just serialization +
journal logging.
"""

from typing import Any, Dict
from pathlib import Path
import json
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO8601 without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def tradeplan_to_contract(trade_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert ExecutionPlanner.TradePlan.to_dict() -> minimal broker ticket.

    trade_plan must contain keys:
      - "accept": bool
      - "final_size": float
      - "tp_pips": float
      - "sl_pips": float
      - "time_stop_bars": int
      - "expected_value": float
      - "reasons": list[str]
      - "meta": {
            "symbol": str,
            "hazard": bool or None,
            "ev_note": str,
            "conformal_decision": str
        }

    NOTE: We don't yet include direction (BUY/SELL). We'll extend ExecutionPlanner
    to include side soon. For now we hardcode "BUY" so the contract schema is stable.
    """
    meta = trade_plan.get("meta", {})
    symbol = meta.get("symbol", "EURUSD")

    contract = {
        "timestamp_utc": _utcnow_iso(),
        "symbol": symbol,
        "side": "BUY",  # Phase 11 placeholder
        "size": float(trade_plan.get("final_size", 0.0)),
        "tp_pips": float(trade_plan.get("tp_pips", 0.0)),
        "sl_pips": float(trade_plan.get("sl_pips", 0.0)),
        "time_stop_bars": int(trade_plan.get("time_stop_bars", 0)),
        "expected_value": float(trade_plan.get("expected_value", 0.0)),
        "accept": bool(trade_plan.get("accept", False)),
        "reasons": list(trade_plan.get("reasons", [])),
        # extra context the EA doesn't strictly need but is great for audit/journal
        "hazard": meta.get("hazard", None),
        "note": meta.get("ev_note", ""),
        "conformal_decision": meta.get("conformal_decision", "UNKNOWN"),
    }

    return contract


def write_next_order(repo_root: str | Path, contract: Dict[str, Any]) -> Path:
    """
    Write the current broker ticket for the EA and also append to journal.

    Creates:
      artifacts/live/next_order.json
          <- polled/consumed by AF_BridgeEA.mq5

      artifacts/journal/trades_YYYYMMDD.jsonl
          <- rolling journal for calibration and post-trade learning
    """
    repo_root = Path(repo_root)

    live_dir = repo_root / "artifacts" / "live"
    journal_dir = repo_root / "artifacts" / "journal"

    live_dir.mkdir(parents=True, exist_ok=True)
    journal_dir.mkdir(parents=True, exist_ok=True)

    # 1. next_order.json (single latest instruction)
    ticket_path = live_dir / "next_order.json"
    ticket_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 2. journal append
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    journal_path = journal_dir / f"trades_{day}.jsonl"
    with journal_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(contract, ensure_ascii=False) + "\n")

    return ticket_path
