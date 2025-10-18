from dataclasses import dataclass, field
from typing import Dict
from .events import MarketEvent, SignalEvent, OrderEvent, FillEvent


@dataclass
class Position:
    qty: float = 0.0
    avg_px: float = 0.0


@dataclass
class Portfolio:
    cash: float = 100_000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    equity: float = 100_000.0

    def on_signal(self, ev: SignalEvent, last_px: float) -> OrderEvent:
        # super-minimal: target of +1 unit for LONG, -1 for SHORT, 0 for FLAT
        target = 1.0 if ev.direction == "LONG" else (-1.0 if ev.direction == "SHORT" else 0.0)
        cur = self.positions.get(ev.symbol, Position()).qty
        qty = target - cur
        side = "BUY" if qty > 0 else ("SELL" if qty < 0 else "FLAT")
        return OrderEvent(ts=ev.ts, symbol=ev.symbol, side=side, qty=abs(qty))

    def on_fill(self, ev: FillEvent):
        p = self.positions.setdefault(ev.symbol, Position())
        if ev.side == "BUY":
            # new avg price
            total_cost = p.avg_px * p.qty + ev.price * ev.qty + ev.commission
            p.qty += ev.qty
            p.avg_px = 0.0 if p.qty == 0 else total_cost / p.qty
            self.cash -= ev.price * ev.qty + ev.commission
        else:
            # selling
            self.cash += ev.price * ev.qty - ev.commission
            p.qty -= ev.qty
            if p.qty == 0:
                p.avg_px = 0.0

    def mark_to_market(self, ev: MarketEvent):
        # mark equity using Close
        unreal = 0.0
        for sym, pos in self.positions.items():
            if pos.qty != 0 and sym in ev.ohlcv_by_sym:
                px = ev.ohlcv_by_sym[sym]["Close"]
                # PnL relative to avg_px
                unreal += (px - pos.avg_px) * pos.qty
        self.equity = self.cash + unreal
