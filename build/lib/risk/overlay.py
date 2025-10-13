# src/risk/overlay.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional, Tuple

__all__ = ["RiskOverlayConfig", "RiskOverlay", "CheckResult"]

CheckResult = Tuple[bool, Dict[str, object]]  # (ok, details)


@dataclass(slots=True)
class RiskOverlayConfig:
    """Toggle which micro-checks the overlay enforces.

    The actual micro-check logic is supplied via callables at construction time.
    That keeps this overlay decoupled from specific modules and avoids import churn.
    """

    enforce_spread: bool = True
    enforce_time_stop: bool = True
    enforce_breakeven_gate: bool = False  # optional


class RiskOverlay:
    """Unified risk overlay (dependency-injected).

    Provide callables for each check you want to enforce:

      - spread_fn(bid: float, ask: float) -> Tuple[bool, float]
          returns (ok, spread_bps)

      - time_stop_fn(bars_elapsed: int, minutes_elapsed: int) -> bool
          returns True if time stop should trigger (i.e., NOT safe to trade)

      - breakeven_fn(side: str, pnl_bps: float) -> Tuple[bool, float]
          returns (arm, trigger_bps). If arm is True, the overlay will report it.

    Any callable can be None — the overlay will silently skip that check.
    """

    def __init__(
        self,
        cfg: RiskOverlayConfig,
        *,
        spread_fn: Optional[Callable[[float, float], Tuple[bool, float]]] = None,
        time_stop_fn: Optional[Callable[[int, int], bool]] = None,
        breakeven_fn: Optional[Callable[[str, float], Tuple[bool, float]]] = None,
    ) -> None:
        self.cfg = cfg
        self._spread_fn = spread_fn
        self._time_stop_fn = time_stop_fn
        self._breakeven_fn = breakeven_fn

    def check(
        self,
        *,
        bid: float,
        ask: float,
        now: Optional[datetime] = None,
        side: Optional[str] = None,
        bars_elapsed: int = 0,
        minutes_elapsed: int = 0,
        pnl_bps: float = 0.0,
    ) -> CheckResult:
        ok = True
        details: Dict[str, object] = {
            "spread_ok": None,
            "spread_bps": None,
            "time_stop": None,
            "breakeven_arm": None,
            "breakeven_bps": None,
        }

        # Spread
        if self.cfg.enforce_spread and self._spread_fn is not None:
            s_ok, s_bps = self._spread_fn(bid, ask)
            details["spread_ok"] = s_ok
            details["spread_bps"] = s_bps
            if not s_ok:
                ok = False

        # Time stop
        if self.cfg.enforce_time_stop and self._time_stop_fn is not None:
            ts = self._time_stop_fn(bars_elapsed, minutes_elapsed)
            details["time_stop"] = ts
            if ts:
                ok = False

        # Break-even gate (does not block trades by itself here; it only informs/arms)
        if self.cfg.enforce_breakeven_gate and self._breakeven_fn is not None and side:
            arm, bps = self._breakeven_fn(side, pnl_bps)
            details["breakeven_arm"] = arm
            details["breakeven_bps"] = bps
            # We intentionally do NOT flip `ok` here; order-routing can decide how to use it.

        return ok, details
