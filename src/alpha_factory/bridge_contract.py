from __future__ import annotations

from typing import Any, Dict
from pathlib import Path
from datetime import datetime, timezone
import json


def _now_utc_iso() -> str:
    """
    Return an ISO8601 UTC timestamp like 2025-10-31T10:22:33Z.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def tradeplan_to_contract(tp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a TradePlan dict into a broker-facing contract.

    Supports both:
    - Phase 12 TradePlan.to_dict() shape:
        {
            "accept": bool,
            "symbol": "EURUSD",
            "side": "BUY",
            "size": 0.35,
            "reasons": [...],
            "exits": {
                "tp_pips": ...,
                "sl_pips": ...,
                "time_stop_bars": ...,
                "expected_value": ...,
            },
        }

    - Legacy Phase 11-ish shape (before ExecutionPlanner started emitting symbol/side/size):
        {
            "accept": True,
            "final_size": 0.42,
            "reasons": [...],
            "tp_pips": 25.0,
            "sl_pips": 12.0,
            "time_stop_bars": 80,
            "expected_value": 0.011,
            "meta": {
                "symbol": "EURUSD",
                "hazard": False,
                "conformal_decision": "ACCEPT",
            },
        }

      In legacy mode we assume BUY for side.
    """

    # symbol:
    symbol = tp.get("symbol")
    if symbol is None:
        meta = tp.get("meta", {})
        symbol = meta.get("symbol", "EURUSD")

    # side:
    side = tp.get("side", "BUY")

    # size:
    # new style: tp["size"]; legacy: tp["final_size"]
    size_val = tp.get("size")
    if size_val is None:
        size_val = tp.get("final_size", 0.0)

    # exits:
    exits_obj = tp.get("exits")
    if exits_obj is None:
        # reconstruct from legacy fields
        exits_obj = {
            "tp_pips": tp.get("tp_pips"),
            "sl_pips": tp.get("sl_pips"),
            "time_stop_bars": tp.get("time_stop_bars"),
            "expected_value": tp.get("expected_value"),
        }

    return {
        "as_of": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size": float(size_val),
        "accept": bool(tp.get("accept", False)),
        "exits": exits_obj,
        "reasons": tp.get("reasons", []),
    }


def write_next_order(repo_root: Path | str, contract: Dict[str, Any]) -> Path:
    """
    Dump the current proposed order to artifacts/live/next_order.json
    for AF_BridgeEA.mq5 to consume.
    Overwrites each time. UTF-8, LF.
    """
    root = Path(repo_root)
    live_dir = root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    out_path = live_dir / "next_order.json"
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(contract, f, ensure_ascii=False)
    return out_path


def append_trade_intent(repo_root: Path | str, contract: Dict[str, Any]) -> Path:
    """
    Append the proposed contract to artifacts/live/journal.ndjson
    as an INTENT entry. This is our audit trail
    before MT5 actually executes.

    We DO NOT rotate/limit here; rotation can be added later.
    """
    root = Path(repo_root)
    live_dir = root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    journal_path = live_dir / "journal.ndjson"

    record = {
        "ts": _now_utc_iso(),
        "type": "INTENT",
        "contract": contract,
    }

    with journal_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return journal_path


def append_trade_fill(repo_root: Path | str, fill: Dict[str, Any]) -> Path:
    """
    After MT5 executes and writes last_fill.json, we ingest that fill and
    append it to journal.ndjson with type="FILL". This closes the audit loop.
    """
    root = Path(repo_root)
    live_dir = root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    journal_path = live_dir / "journal.ndjson"

    record = {
        "ts": _now_utc_iso(),
        "type": "FILL",
        "fill": fill,
    }

    with journal_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return journal_path


# --- Backward-compat shims for older tests / scripts ---


def record_intent(repo_root: Path | str, contract: Dict[str, Any]) -> Path:
    """
    Back-compat alias for append_trade_intent().
    Older code/tests may still call record_intent(...).
    """
    return append_trade_intent(repo_root, contract)


def record_fill(repo_root: Path | str, fill: Dict[str, Any]) -> Path:
    """
    Back-compat alias for append_trade_fill().
    Older code/tests may still call record_fill(...).
    """
    return append_trade_fill(repo_root, fill)
