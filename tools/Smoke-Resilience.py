from datetime import datetime, timezone, timedelta
from src.risk.guards import CircuitBreaker, TimeThrottle, ConcurrencyGate


def main() -> int:
    # CircuitBreaker
    cb = CircuitBreaker(threshold=2, cooldown_sec=2)
    now = datetime.now(timezone.utc)
    assert cb.allow(now)
    cb.record(False, now)
    assert cb.allow(now)
    cb.record(False, now)  # reaches threshold -> trip
    assert not cb.allow(now)  # blocked during cooldown
    assert not cb.allow(now + timedelta(seconds=1))
    assert cb.allow(now + timedelta(seconds=3))  # cooldown over
    cb.record(True, now)  # success resets

    # TimeThrottle
    th = TimeThrottle(min_gap_sec=2)
    t0 = datetime.now(timezone.utc)
    assert th.allow("k", t0)
    assert not th.allow("k", t0 + timedelta(seconds=1))
    assert th.allow("k", t0 + timedelta(seconds=2))

    # ConcurrencyGate
    cg = ConcurrencyGate(max_inflight=2)
    assert cg.try_acquire()
    assert cg.try_acquire()
    assert not cg.try_acquire()
    cg.release()
    assert cg.try_acquire()

    print("Resilience smoke OK")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
