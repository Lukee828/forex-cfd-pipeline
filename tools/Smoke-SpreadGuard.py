# tools/Smoke-SpreadGuard.py
from __future__ import annotations

from src.risk.spread_guard import SpreadGuardConfig, check_spread_ok


def main() -> int:
    # CASE 1: Narrow ~0.8 bps -> OK under 10 bps
    bid, ask = 1.25, 1.2501
    ok, bps = check_spread_ok(bid, ask, cfg=SpreadGuardConfig(max_bps=10.0))
    print("CASE1 ok:", ok, "bps:", round(bps, 3))
    assert ok and 0.79 <= bps <= 0.81

    # CASE 2: Wider ~48 bps -> NOT OK under 20 bps
    bid2, ask2 = 1.25, 1.2560  # ~0.006 / ~1.253 -> ~47.9 bps
    ok2, bps2 = check_spread_ok(bid2, ask2, cfg=SpreadGuardConfig(max_bps=20.0))
    print("CASE2 ok:", ok2, "bps:", round(bps2, 3))
    assert (not ok2) and 47.5 <= bps2 <= 48.5

    print("Smoke-SpreadGuard OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
