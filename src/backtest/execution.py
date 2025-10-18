# src/backtest/execution.py
from dataclasses import dataclass
from typing import Dict
from .events import OrderEvent, FillEvent


@dataclass
class PaperBroker:
    """
    Turns OrderEvent into FillEvent at provided price in the MarketEvent payload.
    Assumes price is available in mkt.ohlcv_by_sym[symbol]["Close"].
    """

    last_prices: Dict[str, float]  # symbol -> last close (kept fresh by caller)

    def on_order(self, order: OrderEvent) -> FillEvent:
        px = self.last_prices.get(order.symbol)
        if px is None:
            # fallback price if missing
            px = 1.0
        side = "BUY" if order.side in ("BUY", "LONG") else "SELL"
        return FillEvent(
            ts=order.ts,
            symbol=order.symbol,
            side=side,
            qty=order.qty,
            price=px,
            commission=0.0,
        )
