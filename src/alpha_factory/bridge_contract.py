# src/alpha_factory/bridge_contract.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
from datetime import datetime, timezone

from alpha_factory.live_guard_config import (
    load_config,
    breach_exists,
    mark_breach,
    LiveConfig,
)
from alpha_factory.live_reconcile import build_execution_report


# ---------------------------------------------------------------------------------
# time helpers / IDs
# ---------------------------------------------------------------------------------


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _journal_path(repo_root: Path) -> Path:
    return Path(repo_root) / "artifacts" / "live" / "journal.ndjson"


def _ticket_path(repo_root: Path) -> Path:
    return Path(repo_root) / "artifacts" / "live" / "next_order.json"


# ---------------------------------------------------------------------------------
# Safety gate BEFORE ticket is written
# ---------------------------------------------------------------------------------


def guard_pretrade_allowed(
    repo_root: Path,
    spread_pips: float,
    last_tick_age_sec: float,
) -> None:
    """
    Raise RuntimeError if we are not allowed to trade right now.

    - global kill switch (live_enabled)
    - BREACH circuit breaker
    - spread limit
    - data staleness / latency limit
    """
    repo_root = Path(repo_root)
    cfg: LiveConfig = load_config(repo_root)

    if not cfg.live_enabled:
        raise RuntimeError("LIVE_DISABLED_BY_CONFIG")

    if breach_exists(repo_root):
        raise RuntimeError("LIVE_DISABLED_BREACH")

    if spread_pips > cfg.max_spread_pips:
        raise RuntimeError(f"SPREAD_TOO_WIDE({spread_pips} pips)")

    # treat last_tick_age_sec as how old the latest price is
    if last_tick_age_sec > cfg.max_latency_sec:
        raise RuntimeError(f"TICK_STALE({last_tick_age_sec} sec)")


# ---------------------------------------------------------------------------------
# Contract building: planner -> broker-facing ticket
# ---------------------------------------------------------------------------------


def _side_from_tp(tp: Dict[str, Any]) -> str:
    # For now we assume long-only BUY. Extend later when we wire direction.
    return "BUY"


def _size_from_tp(tp: Dict[str, Any]) -> float:
    # "final_size" already has ConformalGate / Hazard / Risk Governor / CostModel throttle baked in.
    return float(tp.get("final_size", 0.0))


def _symbol_from_tp(tp: Dict[str, Any]) -> str:
    meta = tp.get("meta", {})
    return str(meta.get("symbol", "EURUSD"))


def _sl_pips_from_tp(tp: Dict[str, Any]) -> float:
    return float(tp.get("sl_pips", 0.0))


def _tp_pips_from_tp(tp: Dict[str, Any]) -> float:
    return float(tp.get("tp_pips", 0.0))


def _time_stop_from_tp(tp: Dict[str, Any]) -> int:
    return int(tp.get("time_stop_bars", 0))


def _ev_from_tp(tp: Dict[str, Any]) -> float:
    return float(tp.get("expected_value", 0.0))


def tradeplan_to_contract(tp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a TradePlan dict (ExecutionPlanner output) into a broker-facing contract.
    This is what gets written to next_order.json for the EA.
    """
    symbol = _symbol_from_tp(tp)
    side = _side_from_tp(tp)
    size = _size_from_tp(tp)

    accept = bool(tp.get("accept", True)) and (size > 0.0)

    contract = {
        "as_of": _now_utc_iso(),
        "ticket_nonce": _now_utc_iso(),  # simple timestamp nonce prevents stale replay
        "symbol": symbol,
        "side": side,
        "size": size,
        "accept": accept,
        "sl_pips": _sl_pips_from_tp(tp),
        "tp_pips": _tp_pips_from_tp(tp),
        "time_stop_bars": _time_stop_from_tp(tp),
        "expected_value": _ev_from_tp(tp),
        # include rationale so EA / audit can see why we did this
        "reasons": tp.get("reasons", []),
    }

    return contract


# ---------------------------------------------------------------------------------
# Journal helpers
# ---------------------------------------------------------------------------------


def append_journal_line(repo_root: Path, row: Dict[str, Any]) -> None:
    """
    Append a single JSON line to artifacts/live/journal.ndjson.
    """
    repo_root = Path(repo_root)
    live_dir = repo_root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    p = _journal_path(repo_root)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_intent(repo_root: Path, contract: Dict[str, Any]) -> None:
    """
    Log the INTENT to trade before sending ticket to MT5 EA.
    """
    row = {
        "ts": _now_utc_iso(),
        "type": "INTENT",
        "contract": contract,
    }
    append_journal_line(repo_root, row)


def append_fill(
    repo_root: Path,
    fill: Dict[str, Any],
) -> None:
    """
    Log a confirmed broker fill (what EA says actually happened).
    """
    row = {
        "ts": _now_utc_iso(),
        "type": "FILL",
        "fill": fill,
    }
    append_journal_line(repo_root, row)


# ---------------------------------------------------------------------------------
# Ticket writer for EA consumption
# ---------------------------------------------------------------------------------


def write_next_order(repo_root: Path, contract: Dict[str, Any]) -> Path:
    """
    Write contract to artifacts/live/next_order.json for AF_BridgeEA.mq5 to read.
    """
    repo_root = Path(repo_root)
    live_dir = repo_root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    tpath = _ticket_path(repo_root)
    tpath.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return tpath


# ---------------------------------------------------------------------------------
# Fill ingestion from EA + postfill risk enforcement
# ---------------------------------------------------------------------------------


def record_fill_from_ea(
    repo_root: Path,
    symbol: str,
    side: str,
    size_exec: float,
    price_exec: float,
    ticket_id: int,
    ticket_nonce: str,
    latency_sec: float,
    slippage_pips: float,
) -> None:
    """
    EA calls this via Bridge-Fill.ps1 after execution.
    """
    repo_root = Path(repo_root)
    # ticket_id from MT5 could be a numeric deal id ("123456789")
    # or a broker ref like "MT5-555". We keep it losslessly as string.
    try:
        ticket_id_clean = int(ticket_id)
    except (TypeError, ValueError):
        ticket_id_clean = str(ticket_id)

    fill_row = {
        "as_of": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size_exec": float(size_exec),
        "price_exec": float(price_exec),
        "ticket_id": ticket_id_clean,
        "ticket_nonce": str(ticket_nonce),
        "latency_sec": float(latency_sec),
        "slippage_pips": float(slippage_pips),
    }

    append_fill(repo_root, fill_row)


def enforce_postfill_limits(repo_root: Path) -> None:
    """
    After logging a FILL, compute execution quality and possibly mark breach.
    If breach is marked, LiveGuard will refuse future tickets automatically.
    """
    repo_root = Path(repo_root)
    cfg: LiveConfig = load_config(repo_root)
    rep = build_execution_report(repo_root)

    # rep keys from live_reconcile.build_execution_report():
    #   "fill_ratio"
    #   "avg_slippage_pips"
    #   "avg_latency_sec"
    avg_slip = float(rep.get("avg_slippage_pips", 0.0))
    avg_lat = float(rep.get("avg_latency_sec", 0.0))

    if avg_slip > cfg.max_slippage_pips:
        mark_breach(
            repo_root,
            f"SLIPPAGE {avg_slip} > {cfg.max_slippage_pips}",
        )
    elif avg_lat > cfg.max_latency_sec:
        mark_breach(
            repo_root,
            f"LATENCY {avg_lat} > {cfg.max_latency_sec}",
        )
