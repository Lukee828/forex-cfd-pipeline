# tools/Smoke-TimeStop.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.risk.time_stop import (
    TimeStopConfig,
    bars_elapsed,
    should_time_stop,
)


def main() -> int:
    now = datetime.now(timezone.utc)

    # CASE1: bars-based stop: entry 6h ago, 1h bars, max_bars=5 => stop (6 >= 5)
    entry1 = now - timedelta(hours=6)
    cfg1 = TimeStopConfig(max_bars=5, bar_seconds=3600)
    stop1, bars1, days1 = should_time_stop(entry1, now, cfg1)
    print("CASE1 stop:", stop1, "bars:", bars1, "days:", days1)
    assert stop1 and bars1 >= 5

    # CASE2: days-based stop: entry 2 days ago, max_days=3 => no stop
    entry2 = now - timedelta(days=2, hours=1)
    cfg2 = TimeStopConfig(max_days=3)
    stop2, bars2, days2 = should_time_stop(entry2, now, cfg2)
    print("CASE2 stop:", stop2, "bars:", bars2, "days:", days2)
    assert (not stop2) and days2 == 2

    # CASE3: both thresholds: entry 3 days ago + 2h, max_days=3, max_bars=10000 => days triggers
    entry3 = now - timedelta(days=3, hours=2)
    cfg3 = TimeStopConfig(max_days=3, max_bars=10_000, bar_seconds=3600)
    stop3, bars3, days3 = should_time_stop(entry3, now, cfg3)
    print("CASE3 stop:", stop3, "bars:", bars3, "days:", days3)
    assert stop3 and days3 >= 3

    # Quick unit for bars_elapsed directly
    be = bars_elapsed(now - timedelta(minutes=90), now, 3600)  # 1.5h -> floor 1 bar
    print("bars_elapsed(90min @1h):", be)
    assert be == 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
