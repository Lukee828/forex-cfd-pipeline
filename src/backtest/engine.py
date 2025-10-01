from queue import Queue
from typing import Iterable, List
from .events import MarketEvent, SignalEvent, OrderEvent, FillEvent
from .portfolio import Portfolio
from .execution import SimulatedBroker
from .strategy.base import Strategy


class Engine:
    def __init__(
        self,
        data_stream: Iterable[MarketEvent],
        strategies: List[Strategy],
        portfolio: Portfolio,
        broker: SimulatedBroker,
    ):
        self.q: "Queue[object]" = Queue()
        self.stream = data_stream
        self.strategies = strategies
        self.portfolio = portfolio
        self.broker = broker

    def run(self):
        for mkt in self.stream:
            # 1) Market in
            self.portfolio.mark_to_market(mkt)
            # 2) Strategies -> Signals
            for strat in self.strategies:
                signals = strat.on_market(mkt)
                for sig in signals:
                    self.q.put(sig)
            # 3) Drain queue synchronously (Signal -> Order -> Fill)
            while not self.q.empty():
                ev = self.q.get()
                if isinstance(ev, SignalEvent):
                    px = mkt.ohlcv_by_sym.get(ev.symbol, {}).get("Close")
                    if px is None:
                        continue
                    order = self.portfolio.on_signal(ev, px)
                    if order.side != "FLAT" and order.qty > 0:
                        self.q.put(order)
                elif isinstance(ev, OrderEvent):
                    px = mkt.ohlcv_by_sym.get(ev.symbol, {}).get("Close")
                    if px is None:
                        continue
                    fill = self.broker.execute(ev, px)
                    if fill:
                        self.q.put(fill)
                elif isinstance(ev, FillEvent):
                    self.portfolio.on_fill(ev)
            # final mark after fills
            self.portfolio.mark_to_market(mkt)
