# src/backtest/event_queue.py
from collections import deque
from typing import Deque, Generic, Optional, TypeVar

T = TypeVar("T")


class EventQueue(Generic[T]):
    """Tiny FIFO event queue used by the event-driven harness."""

    def __init__(self) -> None:
        self._q: Deque[T] = deque()

    def put(self, ev: T) -> None:
        self._q.append(ev)

    def get(self) -> Optional[T]:
        return self._q.popleft() if self._q else None

    def empty(self) -> bool:
        return not self._q

    def __len__(self) -> int:  # pragma: no cover
        return len(self._q)
