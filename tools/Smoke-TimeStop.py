from datetime import datetime, timedelta, timezone
from src.risk.time_stop import TimeStopConfig, should_time_stop, is_time_stop


def main() -> int:
    cfg = TimeStopConfig(max_bars=5, max_days=0)

    # datetime-based API
    now = datetime.now(timezone.utc)
    entry = now - timedelta(hours=6)
    stop1, b1, d1 = should_time_stop(entry, now, bar_minutes=60, cfg=cfg)
    assert stop1 and b1 == 6 and d1 == 0

    # bars/days alias API
    stop2, b2, d2 = is_time_stop(6, 0, cfg)
    assert stop2 and b2 == 6 and d2 == 0
    print("smoke OK")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(0) if main() == 0 else sys.exit(1)
