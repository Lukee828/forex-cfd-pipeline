"""
alpha_factory.regime_hazard
Phase 7 (Regime Hazard / BOCPD throttle)

Goal:
- Detect regime flips (volatility / structure shock).
- Emit a hazard flag + cooldown suggestion.
- Allocator / Risk Governor can size down or embargo new risk during hazard.

This is an MVP detector based on volatility spike z-score. We'll be able to
swap in BOCPD later without changing downstream code.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime, timezone
import pathlib
import json
import numpy as np


@dataclass
class RegimeHazardState:
    as_of: str
    hazard: bool
    reason: str
    score: float
    cooldown_bars: int = 30  # "embargo" window after flip / spike


class RegimeHazard:
    def __init__(self, threshold: float = 2.0):
        """
        threshold: abs(z) above this => hazard.
        We'll extend this later with richer BOCPD hazard models.
        """
        self.threshold = threshold
        self.latest: Optional[RegimeHazardState] = None

    def update_from_vol_series(self, vol_series: "np.ndarray") -> RegimeHazardState:
        """
        vol_series: 1D array of realized vol / ATR / spread-normalized range etc.
        We compute a simple z-score of the last point vs prior window mean/std.

        Returns a RegimeHazardState snapshot and stores it on self.latest.
        """
        if vol_series.ndim != 1 or vol_series.shape[0] < 20:
            # Not enough context to evaluate hazard
            state = RegimeHazardState(
                as_of=_utcnow_iso(),
                hazard=False,
                reason="insufficient_history",
                score=0.0,
                cooldown_bars=30,
            )
            self.latest = state
            return state

        baseline = vol_series[:-1]
        latest = float(vol_series[-1])

        mean = float(np.mean(baseline))
        std = float(np.std(baseline) + 1e-8)

        z = (latest - mean) / std
        score = abs(z)
        hazard_flag = score > self.threshold

        state = RegimeHazardState(
            as_of=_utcnow_iso(),
            hazard=hazard_flag,
            reason="vol_spike" if hazard_flag else "stable",
            score=score,
            cooldown_bars=30,
        )
        self.latest = state
        return state

    def save_status(self, out_dir: str | pathlib.Path) -> pathlib.Path:
        """
        Write latest hazard snapshot to artifacts/regime/latest_regime.json
        plus timestamped backup if you want to extend later.
        """
        if self.latest is None:
            raise RuntimeError("No hazard state available. Call update_from_vol_series() first.")

        out_dir = pathlib.Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        latest_path = out_dir / "latest_regime.json"
        with latest_path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self.latest), f, ensure_ascii=False, indent=2)

        # timestamped archive (optional historical trace)
        ts = self.latest.as_of.replace(":", "-")
        archive_path = out_dir / f"regime_{ts}.json"
        with archive_path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self.latest), f, ensure_ascii=False, indent=2)

        return latest_path

    @staticmethod
    def load_latest(in_dir: str | pathlib.Path) -> RegimeHazardState:
        """
        Runtime hook: allocator / Risk Governor calls this before sizing.
        """
        in_dir = pathlib.Path(in_dir)
        latest_path = in_dir / "latest_regime.json"
        raw = json.loads(latest_path.read_text(encoding="utf-8"))
        return RegimeHazardState(**raw)


def _utcnow_iso() -> str:
    # RFC-ish UTC timestamp without TZ ambiguity
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
