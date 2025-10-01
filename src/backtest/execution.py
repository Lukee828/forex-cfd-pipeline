from .events import OrderEvent, FillEvent


class SimulatedBroker:
    def __init__(self, commission_per_trade: float = 0.0, slip_bps: float = 0.0):
        self.commission = commission_per_trade
        self.slip_bps = slip_bps

    def execute(self, order: OrderEvent, last_price: float) -> FillEvent | None:
        if order.side == "FLAT" or order.qty == 0:
            return None
        # simple bps slippage toward worse side
        slip_mult = 1.0 + (self.slip_bps / 10_000.0) * (
            1 if order.side == "BUY" else -1
        )
        fill_px = last_price * slip_mult
        side = "BUY" if order.side == "BUY" else "SELL"
        return FillEvent(
            ts=order.ts,
            symbol=order.symbol,
            side=side,
            qty=order.qty,
            price=fill_px,
            commission=self.commission,
        )
