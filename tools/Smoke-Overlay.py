from __future__ import annotations

from typing import Callable, Tuple

from src.risk.overlay import RiskOverlay, RiskOverlayConfig
from src.risk.time_stop import TimeStopConfig, is_time_stop

# --- helpers ---------------------------------------------------------------


def simple_spread_fn(bid: float, ask: float, max_bps: float = 25.0) -> Tuple[bool, float]:
    # bps on bid for FX-style quote
    bps = (ask - bid) / bid * 10_000.0
    return (bps <= max_bps, bps)


def time_stop_wrapper(max_bars: int) -> Callable[[int, int], bool]:
    cfg = TimeStopConfig(max_bars=max_bars, max_days=0)

    def _fn(bars_elapsed: int, minutes_elapsed: int) -> bool:
        days = minutes_elapsed // (60 * 24)
        stop, _, _ = is_time_stop(bars_elapsed, days, cfg)
        return stop

    return _fn


# If you want to guard time_stop with a breaker, wire it here.
# Keeping it simple/inline to avoid indentation/paren gotchas.
def build_overlay() -> RiskOverlay:
    cfg = RiskOverlayConfig()
    ts = time_stop_wrapper(max_bars=5)
    return RiskOverlay(
        cfg,
        spread_fn=simple_spread_fn,
        time_stop_fn=ts,
        breakeven_fn=None,
    )


# --- smoke -----------------------------------------------------------------


def main() -> int:
    overlay = build_overlay()

    ok1, d1 = overlay.check(bid=1.25, ask=1.2501, bars_elapsed=3, minutes_elapsed=0)
    print(f"CASE1 {d1}")
    assert ok1

    ok2, d2 = overlay.check(bid=1.25, ask=1.2501, bars_elapsed=6, minutes_elapsed=0)
    print(f"CASE2 {d2}")
    assert not ok2

    print("smoke OK")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
