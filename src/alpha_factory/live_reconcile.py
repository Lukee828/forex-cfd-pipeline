from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime


def _read_journal(journal_path: Path) -> List[Dict[str, Any]]:
    if not journal_path.exists():
        return []
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            # ignore malformed
            continue
    return out


def _parse_iso(ts: str) -> datetime:
    # journal timestamps are iso-ish UTC like "2025-10-31T10:22:55Z"
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def pair_intents_and_fills(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Returns list of dicts like:
    {
      "symbol": "EURUSD",
      "intent_time": "...",
      "fill_time": "... or None",
      "intent_size": 0.35,
      "fill_size": 0.32,
      "latency_sec": 1.8,
      "slippage_pips": 0.7,
      "status": "FILLED" / "NOFILL" / "PARTIAL"
    }
    Matching rule (simple for now):
    - For each INTENT, take the first FILL with same symbol and side
      that occurs after it.
    """
    intents = [r for r in rows if r.get("type") == "INTENT"]
    fills = [r for r in rows if r.get("type") == "FILL"]

    results: List[Dict[str, Any]] = []

    for intent in intents:
        sym = intent.get("symbol")
        side = intent.get("side")
        intent_ts = intent.get("ts_utc")
        intent_size = float(intent.get("size", 0.0))
        intent_price = float(intent.get("price_request", 0.0))

        # find first compatible fill after intent time
        t_intent = _parse_iso(intent_ts) if intent_ts else None
        chosen = None
        for f in fills:
            if f.get("symbol") != sym:
                continue
            if f.get("side") != side:
                continue
            f_ts = f.get("ts_utc")
            if f_ts and t_intent and _parse_iso(f_ts) < t_intent:
                continue  # fill before intent? skip
            chosen = f
            break

        if chosen is None:
            results.append(
                {
                    "symbol": sym,
                    "intent_time": intent_ts,
                    "fill_time": None,
                    "intent_size": intent_size,
                    "fill_size": 0.0,
                    "latency_sec": None,
                    "slippage_pips": None,
                    "status": "NOFILL",
                }
            )
            continue

        fill_ts = chosen.get("ts_utc")
        fill_size = float(chosen.get("size", 0.0))
        fill_price = float(chosen.get("price_exec", 0.0))

        latency_sec = None
        if intent_ts and fill_ts:
            latency_sec = (_parse_iso(fill_ts) - _parse_iso(intent_ts)).total_seconds()

        # extremely naive pips math, assume 1 pip = 0.0001
        pip = 0.0001
        if side == "BUY":
            slippage_pips = (fill_price - intent_price) / pip
        else:
            slippage_pips = (intent_price - fill_price) / pip

        status = "FILLED"
        if 0.0 < fill_size < intent_size:
            status = "PARTIAL"
        elif fill_size == 0.0:
            status = "NOFILL"

        results.append(
            {
                "symbol": sym,
                "intent_time": intent_ts,
                "fill_time": fill_ts,
                "intent_size": intent_size,
                "fill_size": fill_size,
                "latency_sec": latency_sec,
                "slippage_pips": slippage_pips,
                "status": status,
            }
        )

    return results


def summarize_execution_quality(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produce rollup stats for dashboard / risk:
    - avg latency
    - avg slippage
    - fill ratio (fills / intents)
    """
    if not pairs:
        return {
            "n_intents": 0,
            "n_fills": 0,
            "fill_ratio": 0.0,
            "avg_latency_sec": None,
            "avg_slippage_pips": None,
        }

    latencies = [p["latency_sec"] for p in pairs if p["latency_sec"] is not None]
    slippages = [p["slippage_pips"] for p in pairs if p["slippage_pips"] is not None]

    n_intents = len(pairs)
    n_fills = sum(1 for p in pairs if p["status"] in ("FILLED", "PARTIAL"))
    fill_ratio = n_fills / n_intents if n_intents else 0.0

    avg_latency = sum(latencies) / len(latencies) if latencies else None
    avg_slip = sum(slippages) / len(slippages) if slippages else None

    return {
        "n_intents": n_intents,
        "n_fills": n_fills,
        "fill_ratio": fill_ratio,
        "avg_latency_sec": avg_latency,
        "avg_slippage_pips": avg_slip,
    }


def build_execution_report(repo_root: str | Path) -> Dict[str, Any]:
    """
    High-level helper:
    - read journal
    - pair INTENT/FILL
    - summarize
    """
    root = Path(repo_root)
    journal_path = root / "artifacts" / "live" / "journal.ndjson"
    rows = _read_journal(journal_path)
    pairs = pair_intents_and_fills(rows)
    summary = summarize_execution_quality(pairs)
    return {
        "summary": summary,
        "pairs": pairs,
    }
