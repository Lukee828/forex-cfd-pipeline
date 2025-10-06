# tools/Smoke-BreakEvenGate.py
from __future__ import annotations

from src.risk.be_gate import (
    BreakEvenGateConfig,
    move_in_favor_bps,
    should_arm_break_even,
)


def approx(a: float, b: float, tol: float = 0.05) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    # CASE1: LONG, moved ~+16.667 bps -> arm when arm_bps=10
    entry1, px1, side1 = 1.2000, 1.2020, "long"
    arm1, bps1 = should_arm_break_even(
        entry1, px1, side1, BreakEvenGateConfig(arm_bps=10.0)
    )
    print("CASE1 arm:", arm1, "bps:", round(bps1, 3))
    # (1.2020-1.2000)/1.2000 * 10_000 = 16.666...
    assert arm1 and approx(bps1, 16.666, 0.01)

    # CASE2: SHORT, moved ~+23.077 bps in favor, but threshold 25 -> don't arm
    entry2, px2, side2 = 1.3000, 1.2970, "short"
    arm2, bps2 = should_arm_break_even(
        entry2, px2, side2, BreakEvenGateConfig(arm_bps=25.0)
    )
    print("CASE2 arm:", arm2, "bps:", round(bps2, 3))
    # For short: favor_bps = 10_000 * (entry - current)/entry = ~23.077
    assert (not arm2) and approx(bps2, 23.077, 0.02)

    # CASE3: exactly at threshold -> arm True
    entry3, px3, side3 = 1.0000, 1.0010, "long"  # +10 bps
    arm3, bps3 = should_arm_break_even(
        entry3, px3, side3, BreakEvenGateConfig(arm_bps=10.0)
    )
    print("CASE3 arm:", arm3, "bps:", round(bps3, 3))
    assert arm3 and approx(bps3, 10.0, 0.001)

    # Direct check of move_in_favor_bps sign flip for short:
    bps_long = move_in_favor_bps(1.0000, 1.0020, "long")  # +20 bps
    bps_short = move_in_favor_bps(1.0000, 0.9980, "short")  # +20 bps in favor
    print("SIGN test long/short:", round(bps_long, 3), round(bps_short, 3))
    assert approx(bps_long, 20.0, 0.001) and approx(bps_short, 20.0, 0.001)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
