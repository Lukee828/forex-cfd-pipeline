# src/backtest/engine_loop.py
"""
Minimal event-driven engine skeleton.

Wire these later:
- feed.next_bar() -> MarketEvent
- strategy.on_market(event) -> List[SignalEvent]
- portfolio.on_market(event), portfolio.on_fill(fill)
- execution.execute(order) -> FillEvent

This module intentionally does not import your concrete classes
to avoid interface coupling until you're ready.
"""
from typing import List, Optional, Protocol, Any
from .event_queue import EventQueue


class MarketEventP(Protocol):
    ts: Any


class SignalEventP(Protocol):
    symbol: str
    direction: str  # "LONG"/"SHORT"/"FLAT"


class OrderEventP(Protocol):
    symbol: str
    side: str  # "BUY"/"SELL"


class FillEventP(Protocol):
    symbol: str
    side: str


class FeedP(Protocol):
    def next_bar(self) -> Optional[MarketEventP]: ...


class StrategyP(Protocol):
    def on_market(self, event: MarketEventP) -> List[SignalEventP]: ...


class PortfolioP(Protocol):
    def on_market(self, event: MarketEventP) -> None: ...
    def on_signal(self, sig: SignalEventP) -> Optional[OrderEventP]: ...
    def on_fill(self, fill: FillEventP) -> None: ...


class ExecutionP(Protocol):
    def execute(self, order: OrderEventP) -> FillEventP: ...


def run_loop(
    feed: FeedP,
    strategy: StrategyP,
    portfolio: PortfolioP,
    execution: ExecutionP,
    max_steps: int = 10_000,
) -> int:
    """Pump a tiny event loop. Returns number of market steps processed."""
    q: EventQueue[object] = EventQueue()
    steps = 0
    while steps < max_steps:
        mkt = feed.next_bar()
        if mkt is None:
            break
        steps += 1
        q.put(mkt)

        # Process market event
        portfolio.on_market(mkt)
        for sig in strategy.on_market(mkt):
            ord_ev = portfolio.on_signal(sig)
            if ord_ev is not None:
                fill = execution.execute(ord_ev)
                portfolio.on_fill(fill)

        # drain any extra events (future expansion)
        while not q.empty():
            _ = q.get()

    return steps
