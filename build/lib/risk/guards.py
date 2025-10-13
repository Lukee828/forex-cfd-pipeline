from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class CircuitBreaker:
    """Trip after `threshold` consecutive failures; open for `cooldown_sec`."""

    threshold: int = 3
    cooldown_sec: int = 60
    _failures: int = 0
    _opened_until: Optional[datetime] = None

    def allow(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        if self._opened_until and now < self._opened_until:
            return False
        # window expired; closed again
        self._opened_until = None
        return True

    def record(self, success: bool, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        if success:
            self._failures = 0
            return
        self._failures += 1
        if self._failures >= self.threshold:
            self._opened_until = now + timedelta(seconds=self.cooldown_sec)
            self._failures = 0  # reset counter when tripped


@dataclass
class TimeThrottle:
    """Enforce a minimum number of seconds between events per key."""

    min_gap_sec: int
    _last: Dict[str, datetime] = field(default_factory=dict)

    def allow(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        prev = self._last.get(key)
        if prev is None or (now - prev).total_seconds() >= self.min_gap_sec:
            self._last[key] = now
            return True
        return False


@dataclass
class ConcurrencyGate:
    """Bound concurrent operations; non-blocking try_acquire/release."""

    max_inflight: int = 1
    _inflight: int = 0

    def try_acquire(self) -> bool:
        if self._inflight >= self.max_inflight:
            return False
        self._inflight += 1
        return True

    def release(self) -> None:
        if self._inflight > 0:
            self._inflight -= 1
