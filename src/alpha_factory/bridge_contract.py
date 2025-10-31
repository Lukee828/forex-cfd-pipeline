from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def tradeplan_to_contract(tp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a TradePlan dict into a broker-facing contract.

    tp keys (from ExecutionPlanner.TradePlan.to_dict()):
        accept: bool
        final_size: float
        tp_pips, sl_pips, time_stop_bars, expected_value
        meta.symbol, meta.hazard, meta.conformal_decision, etc.
    """
    symbol = tp.get("meta", {}).get("symbol", "EURUSD")
    size = float(tp.get("final_size", 0.0))

    # TODO Phase 13+: side from planner/meta, not hardcoded.
    # We'll assume BUY for now.
    side = "BUY"

    contract = {
        "as_of": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size": size,
        "accept": bool(tp.get("accept", False)),
        "tp_pips": float(tp.get("tp_pips", 0.0)),
        "sl_pips": float(tp.get("sl_pips", 0.0)),
        "time_stop_bars": int(tp.get("time_stop_bars", 0)),
        "expected_value": float(tp.get("expected_value", 0.0)),
        "reasons": list(tp.get("reasons", [])),
        "meta": dict(tp.get("meta", {})),
    }
    return contract


def _ticket_signature(contract: Dict[str, Any]) -> str:
    """
    Hash a few stable fields so we can detect duplicate spam.
    """
    key_parts = [
        str(contract.get("symbol", "")),
        str(contract.get("side", "")),
        f"{contract.get('size',0.0):.5f}",
        f"{contract.get('tp_pips',0.0):.1f}",
        f"{contract.get('sl_pips',0.0):.1f}",
    ]
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_live_guard_config(repo_root: Path) -> Dict[str, Any]:
    cfg_path = repo_root / "artifacts" / "live" / "live_guard_config.json"
    return _read_json(
        cfg_path,
        {
            "live_enabled": False,
            "max_spread_pips": 2.5,
            "max_age_sec": 5,
            "min_size": 0.05,
            "max_size": 1.00,
            "dup_window_sec": 30,
        },
    )


def safety_filter_contract(
    contract: Dict[str, Any],
    cfg: Dict[str, Any],
    market_spread_pips: Optional[float],
    model_age_sec: Optional[float],
) -> Dict[str, Any]:
    """
    Enforce live_enabled, spread, staleness, size limits.
    If anything violates, force accept=False and add reason.
    """
    reasons = list(contract.get("reasons", []))
    ok = contract.get("accept", False)

    # live_enabled gate
    if not bool(cfg.get("live_enabled", False)):
        ok = False
        reasons.append("live_disabled")

    # spread gate
    if market_spread_pips is not None:
        max_spread = float(cfg.get("max_spread_pips", 9999.0))
        if market_spread_pips > max_spread:
            ok = False
            reasons.append(f"spread_{market_spread_pips:.2f}_gt_{max_spread:.2f}")

    # staleness gate (e.g. hazard snapshot age)
    if model_age_sec is not None:
        max_age = float(cfg.get("max_age_sec", 9999.0))
        if model_age_sec > max_age:
            ok = False
            reasons.append(f"stale_{model_age_sec:.1f}s_gt_{max_age:.1f}s")

    # size sanity
    size = float(contract.get("size", 0.0))
    if size < float(cfg.get("min_size", 0.0)):
        ok = False
        reasons.append("size_below_min")
    if size > float(cfg.get("max_size", 9999.0)):
        ok = False
        reasons.append("size_above_max")

    contract["accept"] = ok
    contract["reasons"] = reasons
    return contract


def dup_filter_contract(
    contract: Dict[str, Any],
    repo_root: Path,
    cfg: Dict[str, Any],
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compare signature of this contract against last fire.
    If same and too soon, force accept=False.
    """
    live_dir = repo_root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    sig_file = live_dir / "last_ticket_signature.json"

    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    sig = _ticket_signature(contract)

    last_info = _read_json(sig_file, default={"sig": None, "ts": 0.0})
    last_sig = last_info.get("sig")
    last_ts = float(last_info.get("ts", 0.0))

    reasons = list(contract.get("reasons", []))
    ok = contract.get("accept", False)

    if last_sig == sig:
        dup_window = float(cfg.get("dup_window_sec", 30.0))
        age = now_ts - last_ts
        if age < dup_window:
            ok = False
            reasons.append(f"duplicate_{age:.1f}s_lt_{dup_window:.1f}s")

    # write current sig (always update, even if blocked)
    to_write = {"sig": sig, "ts": now_ts}
    _write_json(sig_file, to_write)

    contract["accept"] = ok
    contract["reasons"] = reasons
    return contract


def write_next_order(repo_root: Path, contract: Dict[str, Any]) -> Path:
    """
    Save contract as the next order ticket for EA.
    """
    out_path = repo_root / "artifacts" / "live" / "next_order.json"
    _write_json(out_path, contract)
    return out_path


def append_trade_intent(journal_path: Path, contract: Dict[str, Any]) -> None:
    """
    Append an INTENT line to journal.ndjson.
    """
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    evt = {
        "event": "INTENT",
        "ts_utc": _now_utc_iso(),
        "contract": contract,
    }
    with journal_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(evt, ensure_ascii=False) + "\n")


def append_trade_fill(
    journal_path: Path,
    ticket_id: str,
    symbol: str,
    price_fill: float,
    filled_size: float,
) -> None:
    """
    Append a FILL line.
    EA or MT5 poller will call this when a trade is actually executed.
    """
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    evt = {
        "event": "FILL",
        "ts_utc": _now_utc_iso(),
        "ticket_id": ticket_id,
        "symbol": symbol,
        "price_fill": price_fill,
        "filled_size": filled_size,
    }
    with journal_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(evt, ensure_ascii=False) + "\n")


def build_live_safe_contract(
    repo_root: Path,
    tp_dict: Dict[str, Any],
    # These two are runtime inputs we’ll later source from MT5 / RegimeHazard age:
    market_spread_pips: Optional[float],
    model_age_sec: Optional[float],
) -> Dict[str, Any]:
    """
    Full pipeline for Phase 13:
    - convert TradePlan -> base contract
    - apply safety_filter_contract()
    - apply dup_filter_contract()
    Returns final contract ready to write.
    """
    repo_root = Path(repo_root).resolve()
    cfg = _load_live_guard_config(repo_root)

    contract = tradeplan_to_contract(tp_dict)

    # safety gates
    contract = safety_filter_contract(
        contract,
        cfg=cfg,
        market_spread_pips=market_spread_pips,
        model_age_sec=model_age_sec,
    )

    # duplicate suppression
    contract = dup_filter_contract(
        contract,
        repo_root=repo_root,
        cfg=cfg,
    )

    return contract

def record_fill_from_ea(
    repo_root: str | Path,
    symbol: str,
    side: str,
    size: float,
    price_exec: float,
    ticket_id: str,
    note: str | None = None,
) -> None:
    """
    Called by AF_BridgeEA.mq5 (Phase 14).
    Appends a FILL row to journal.ndjson.
    """
    root = Path(repo_root)
    live_dir = root / "artifacts" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    row = {
        "type": "FILL",
        "ts_utc": _now_utc_iso(),
        "symbol": symbol,
        "side": side,
        "size": size,
        "price_exec": price_exec,
        "ticket_id": ticket_id,
        "note": note or "",
    }

    with (live_dir / "journal.ndjson").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
