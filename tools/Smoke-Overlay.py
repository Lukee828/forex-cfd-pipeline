# tools/Smoke-Overlay.py
from __future__ import annotations

from src.risk.overlay import RiskOverlay, RiskOverlayConfig

# Integrate with existing micro-checks (SpreadGuard + TimeStop).
from src.risk.spread_guard import SpreadGuardConfig, check_spread_ok
import src.risk.time_stop as ts_mod

TimeStopConfig = ts_mod.TimeStopConfig
is_time_stop = getattr(ts_mod, "is_time_stop", None) or getattr(
    ts_mod, "should_time_stop", None
)
if is_time_stop is None:
    raise ImportError(
        "time_stop API missing: need is_time_stop() or should_time_stop()"
    )


def spread_wrapper(max_bps: float):
    cfg = SpreadGuardConfig(max_bps=max_bps)

    def _fn(bid: float, ask: float):
        ok, bps = check_spread_ok(bid, ask, cfg=cfg)
        return ok, bps

    return _fn


def time_stop_wrapper(max_bars: int, max_minutes: int):
    cfg = TimeStopConfig(max_bars=max_bars, max_days=max_minutes // (60 * 24))

    def _fn(bars_elapsed: int, minutes_elapsed: int):
        days = minutes_elapsed // (60 * 24)
        return is_time_stop(bars_elapsed, days, cfg)

    return _fn


def approx(x: float, y: float, eps: float = 1e-6) -> bool:
    return abs(x - y) <= eps


def main() -> int:
    # Overlay with both spread + time-stop enabled
    overlay = RiskOverlay(
        RiskOverlayConfig(
            enforce_spread=True, enforce_time_stop=True, enforce_breakeven_gate=False
        ),
        spread_fn=spread_wrapper(max_bps=20.0),
        time_stop_fn=time_stop_wrapper(max_bars=5, max_days=0),
    )

    # CASE 1: Tight spread ~8 bps (OK) + within time (OK) -> overall OK
    ok1, d1 = overlay.check(bid=1.25, ask=1.2501, bars_elapsed=3, minutes_elapsed=64800)
    print(
        "CASE1 ok:",
        ok1,
        "spread_bps:",
        round(d1["spread_bps"], 3),
        "time_stop:",
        d1["time_stop"],
    )
    assert (
        ok1
        and d1["spread_ok"]
        and (d1["time_stop"] is False)
        and approx(round(d1["spread_bps"], 3), 8.0, 0.05)
    )

    # CASE 2: Wide spread ~48 bps (NOT OK) + within time (OK) -> overall NOT OK
    ok2, d2 = overlay.check(bid=1.25, ask=1.2526, bars_elapsed=3, minutes_elapsed=64800)
    print(
        "CASE2 ok:",
        ok2,
        "spread_bps:",
        round(d2["spread_bps"], 3),
        "time_stop:",
        d2["time_stop"],
    )
    assert (
        (not ok2)
        and (d2["time_stop"] is False)
        and approx(round(d2["spread_bps"], 3), 48.0, 0.1)
    )

    # CASE 3: Tight spread (OK) but time-stop triggers (bars over) -> overall NOT OK
    ok3, d3 = overlay.check(
        bid=1.1000, ask=1.1001, bars_elapsed=9, minutes_elapsed=43200
    )
    print(
        "CASE3 ok:",
        ok3,
        "spread_bps:",
        round(d3["spread_bps"], 3),
        "time_stop:",
        d3["time_stop"],
    )
    assert (not ok3) and d3["spread_ok"] and (d3["time_stop"] is True)

    print("Overlay smoke OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
