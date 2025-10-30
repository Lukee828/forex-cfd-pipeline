"""
alpha_factory.cost_model
Phase 9 (Cost Model / Execution Throttle)

Goal:
- Block or scale trades if execution costs are temporarily bad.
- This is the last gate before actually sending an order.

We snapshot cost conditions (spread, liquidity regime)
into artifacts/cost/latest_cost.json via a nightly (or intraday) PS7 job.

AllocationDecider (Phase 8) will be extended to multiply final_size by
this cost multiplier, and can hard-block if multiplier == 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
from datetime import datetime, timezone
import json
import pathlib


@dataclass
class CostSnapshot:
    as_of: str
    symbol: str
    liquidity_band: str  # e.g. "OK", "THIN", "DEAD"
    cost_multiplier: float  # 1.0 normal, 0.6 thin, 0.0 don't trade
    note: str = ""


class CostModel:
    """
    Lightweight accessor around the latest cost snapshot.

    Future: we could make this symbol-specific, per-session, etc.
    For now we assume one symbol snapshot is representative, or
    that we run per-symbol and choose the relevant one.
    """

    def __init__(self, snapshot: CostSnapshot):
        self.snapshot = snapshot

    @staticmethod
    def load_latest(in_dir: str | pathlib.Path) -> "CostModel":
        in_dir = pathlib.Path(in_dir)
        path = in_dir / "latest_cost.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        snap = CostSnapshot(**raw)
        return CostModel(snapshot=snap)

    def get_multiplier_for_trade(
        self,
        symbol: str,
        context: Dict[str, Any] | None = None,
    ) -> float:
        """
        Decide execution multiplier to apply *right now*.
        For now:
        - if liquidity is DEAD => 0.0
        - if THIN => 0.6
        - if OK => 1.0
        Later: we can blend in per-symbol stats, slippage expectations,
        spread deviation from baseline, rollover windows, etc.
        """
        band = self.snapshot.liquidity_band.upper()

        if band == "DEAD":
            return 0.0
        if band == "THIN":
            return 0.6
        return 1.0  # OK / default


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_cost_snapshot(
    out_dir: str | pathlib.Path,
    symbol: str,
    liquidity_band: str,
    cost_multiplier: float,
    note: str = "",
) -> pathlib.Path:
    """
    Helper to persist a new snapshot (used by Cost-Calibrate.ps1).
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snap = CostSnapshot(
        as_of=_utcnow_iso(),
        symbol=symbol,
        liquidity_band=liquidity_band,
        cost_multiplier=float(cost_multiplier),
        note=note,
    )
    data = asdict(snap)

    latest_path = out_dir / "latest_cost.json"
    latest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # timestamped archive
    ts = snap.as_of.replace(":", "-")
    archive_path = out_dir / f"cost_{ts}.json"
    archive_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return latest_path
