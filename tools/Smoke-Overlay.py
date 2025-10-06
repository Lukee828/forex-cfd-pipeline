from __future__ import annotations
from typing import Tuple
from src.risk.overlay import RiskOverlay, RiskOverlayConfig
from src.risk.time_stop import TimeStopConfig, is_time_stop


def time_stop_wrapper(max_bars: int):
    cfg = TimeStopConfig(max_bars=max_bars, max_days=0)

    def _fn(bars_elapsed: int, minutes_elapsed: int) -> bool:
        days = minutes_elapsed // (60 * 24)
        stop, _, _ = is_time_stop(bars_elapsed, days, cfg)
        return stop

    return _fn


def spread_fn(bid: float, ask: float) -> Tuple[bool, float]:
    mid = (bid + ask) / 2.0
    bps = (ask - bid) / mid * 1e4
    return (bps <= 25.0, bps)


def breakeven_fn(side: str, entry_price: float) -> Tuple[bool, float]:
    return (True, 10.0)


def main() -> int:
    cfg = RiskOverlayConfig()
    overlay = RiskOverlay(
        cfg,
        spread_fn=spread_fn,
        time_stop_fn=time_stop_wrapper(max_bars=5),
        breakeven_fn=breakeven_fn,
    )

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
