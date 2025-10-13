from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpreadGuardConfig:
    """
    Basic config for a spread sanity check.

    max_bps   : reject if (ask - bid)/mid * 10_000 > max_bps
    min_abs   : reject if (ask - bid) > min_abs (absolute price units), optional
    require_px: if True, also require a nearby reference price (e.g., last/close)
    """

    max_bps: float = 5.0
    min_abs: Optional[float] = None
    require_px: bool = False


def _mid(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0:
        raise ValueError("bid/ask must be positive")
    if ask < bid:
        raise ValueError("ask must be >= bid")
    return 0.5 * (bid + ask)


def spread_bps(bid: float, ask: float) -> float:
    mid = _mid(bid, ask)
    return (ask - bid) / mid * 10_000.0


def check_spread_ok(
    bid: float,
    ask: float,
    px_ref: Optional[float] = None,
    cfg: SpreadGuardConfig = SpreadGuardConfig(),
) -> tuple[bool, float]:
    """
    Returns (ok, bps). ok=False means guard recommends rejecting new orders.

    If cfg.require_px is True and px_ref is None, treat as not-ok.
    If cfg.min_abs is set and (ask - bid) > min_abs, not-ok.
    Always check max_bps against computed bps.
    """
    bps = spread_bps(bid, ask)

    if cfg.require_px and px_ref is None:
        return (False, bps)

    if cfg.min_abs is not None and (ask - bid) > cfg.min_abs:
        return (False, bps)

    if cfg.max_bps is not None and bps > cfg.max_bps:
        return (False, bps)

    return (True, bps)
