from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BreakEvenGateConfig",
    "move_in_favor_bps",
    "should_arm_break_even",
]


@dataclass(frozen=True)
class BreakEvenGateConfig:
    """Arm BE only after price has moved in our favor by >= arm_bps (relative bps)."""

    arm_bps: float = 10.0  # e.g., require +10 bps in our favor before arming BE


def _sign_for_side(side: str) -> int:
    s = side.lower()
    if s == "long":
        return +1
    if s == "short":
        return -1
    raise ValueError("side must be 'long' or 'short'")


def move_in_favor_bps(entry_price: float, current_price: float, side: str) -> float:
    """Return relative basis points the market has moved in our favor since entry.

    bps = 10_000 * sign(side) * (current - entry) / entry
    For long:   positive if current > entry
    For short:  positive if current < entry
    """
    if entry_price <= 0.0:
        raise ValueError("entry_price must be > 0")
    sign = _sign_for_side(side)
    rel = (current_price - entry_price) / entry_price
    return 10_000.0 * sign * rel


def should_arm_break_even(
    entry_price: float, current_price: float, side: str, cfg: BreakEvenGateConfig
) -> tuple[bool, float]:
    """Return (arm: bool, favor_bps: float)."""
    favor_bps = move_in_favor_bps(entry_price, current_price, side)
    return (favor_bps >= cfg.arm_bps, favor_bps)
