"""
alpha_factory.ev_exit
Phase 10 (EV Exit Planner)

Goal:
- Recommend TP/SL/time-stop for a new trade based on learned expected value.
- Persist nightly to artifacts/ev/latest_ev_exit.json via EV-Calibrate.ps1.
- Later this will use real trade/journal outcomes (PnL surfaces).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any
from datetime import datetime, timezone
import json
import pathlib
import random


@dataclass
class ExitPolicy:
    as_of: str
    tp_pips: float
    sl_pips: float
    time_stop_bars: int
    expected_value: float  # e.g. +0.012 means +1.2% expectancy on risk
    note: str = ""


class EVExitPlanner:
    """
    A tiny wrapper around an ExitPolicy.
    Future: Instead of a single global policy, this becomes conditional
    on regime features / signal strength / symbol.
    """

    def __init__(self, policy: ExitPolicy):
        self.policy = policy

    @staticmethod
    def load_latest(in_dir: str | pathlib.Path) -> "EVExitPlanner":
        in_dir = pathlib.Path(in_dir)
        path = in_dir / "latest_ev_exit.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        pol = ExitPolicy(**raw)
        return EVExitPlanner(pol)

    def propose_exit_plan(
        self,
        features: Dict[str, Any],
        symbol: str = "EURUSD",
    ) -> Dict[str, Any]:
        """
        Return a dict describing how we should manage this trade:
        - take-profit distance
        - stop-loss distance
        - time stop
        - EV tag
        """
        # Placeholder: ignore features, just return the stored policy.
        return {
            "symbol": symbol,
            "tp_pips": self.policy.tp_pips,
            "sl_pips": self.policy.sl_pips,
            "time_stop_bars": self.policy.time_stop_bars,
            "expected_value": self.policy.expected_value,
            "note": self.policy.note,
            "as_of": self.policy.as_of,
        }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def synth_fit_ev_policy() -> ExitPolicy:
    """
    Stand-in for a real EV surface fit.
    Right now we just pretend we evaluated a handful of TP/SL/time-stop combos
    and picked the best EV.

    Later you'll compute this from actual trade outcomes.
    """

    # pretend we "evaluated" some combos
    candidates = [
        # tp_pips, sl_pips, time_stop_bars, EV
        (20.0, 10.0, 60, 0.010, "tight RR, quick scalp"),
        (30.0, 15.0, 90, 0.012, "balanced swing"),
        (50.0, 20.0, 180, 0.008, "runner bias"),
    ]

    # pick highest EV (ties random)
    max_ev = max(c[3] for c in candidates)
    best = [c for c in candidates if c[3] == max_ev]
    tp_pips, sl_pips, ts_bars, ev, note = random.choice(best)

    return ExitPolicy(
        as_of=_utcnow_iso(),
        tp_pips=tp_pips,
        sl_pips=sl_pips,
        time_stop_bars=ts_bars,
        expected_value=ev,
        note=note,
    )


def write_ev_policy(out_dir: str | pathlib.Path, policy: ExitPolicy) -> pathlib.Path:
    """
    Persist the chosen EV exit policy:
    - artifacts/ev/latest_ev_exit.json
    - artifacts/ev/ev_exit_<timestamp>.json
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = asdict(policy)

    latest_path = out_dir / "latest_ev_exit.json"
    latest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ts = policy.as_of.replace(":", "-")
    archive_path = out_dir / f"ev_exit_{ts}.json"
    archive_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return latest_path
