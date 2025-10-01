# src/backtest/engine.py
"""
Minimal event-driven backtest engine:
- Events: MARKET, SIGNAL, ORDER, FILL
- MarketData feed dispatches bars/ticks
- Broker sim applies slippage/latency/fills (market & limit)
- Portfolio tracks positions, cash, PnL
- Attribution: per-symbol, per-sleeve
"""

from dataclasses import dataclass
from typing import Dict, Optional, Iterable
import pandas as pd
import numpy as np


# --------- Events ---------
@dataclass
class MarketEvent:
    ts: pd.Timestamp
    symbol: str
    px_open: float
    px_high: float
    px_low: float
    px_close: float
    volume: float


@dataclass
class SignalEvent:
    ts: pd.Timestamp
    symbol: str
    sleeve: str  # e.g. "TF", "MR", "VOL"
    direction: int  # -1, 0, +1
    strength: float  # 0..1 (used for sizing)


@dataclass
class OrderEvent:
    ts: pd.Timestamp
    symbol: str
    side: str  # BUY / SELL
    qty: float  # (lots or shares)
    order_type: str  # MARKET / LIMIT
    limit_px: Optional[float] = None
    sleeve: str = "NA"


@dataclass
class FillEvent:
    ts: pd.Timestamp
    symbol: str
    side: str
    qty: float
    px: float
    slippage: float
    order_id: str
    sleeve: str = "NA"


# --------- MarketData ---------
class MarketData:
    """Iterator of MarketEvent from a dict[symbol] -> DataFrame(OHLCV, index=ts)."""

    def __init__(self, ohlcv: Dict[str, pd.DataFrame]):
        self.ohlcv = {s: df.sort_index() for s, df in ohlcv.items()}
        self._iters = {s: df.itertuples() for s, df in self.ohlcv.items()}

    def __iter__(self) -> Iterable[MarketEvent]:
        # merge by time in a naïve round-robin; for daily bars this is ok
        # for intraday, pre-align an outer join by timestamp
        frames = []
        for s, df in self.ohlcv.items():
            x = df.copy()
            x["symbol"] = s
            frames.append(x)
        all_bars = pd.concat(frames).sort_index()
        for ts, row in all_bars.groupby(level=0):
            for _, r in row.iterrows():
                yield MarketEvent(
                    ts=ts,
                    symbol=r["symbol"],
                    px_open=float(r["open"]),
                    px_high=float(r["high"]),
                    px_low=float(r["low"]),
                    px_close=float(r["close"]),
                    volume=float(r.get("volume", 0.0)),
                )


# --------- Broker (sim) ---------
class SimBroker:
    """
    Simple fill logic:
      - MARKET: fill at close +/- slippage_bps
      - LIMIT: fill if bar trades through limit (high/low), at limit +/- slip
    Costs: commission_per_lot (flat), spread_bps (on price)
    """

    def __init__(
        self, slippage_bps=1.0, spread_bps=0.0, commission_per_lot=0.0, seed=7
    ):
        self.slip = float(slippage_bps)
        self.spread = float(spread_bps)
        self.comm = float(commission_per_lot)
        self.rng = np.random.default_rng(seed)
        self.order_id = 0

    def _slip_px(self, px: float, side: str) -> float:
        # add spread to disadvantage and slip randomly around it
        sgn = +1 if side.upper() == "BUY" else -1
        spread = px * (self.spread / 1e4) * sgn
        slip = px * (self.slip / 1e4) * sgn * (0.5 + self.rng.random())
        return px + spread + slip

    def try_fill(self, bar: MarketEvent, order: OrderEvent) -> Optional[FillEvent]:
        if order.order_type == "MARKET":
            px = self._slip_px(bar.px_close, order.side)
            self.order_id += 1
            return FillEvent(
                bar.ts,
                order.symbol,
                order.side,
                order.qty,
                px,
                self.slip,
                f"O{self.order_id}",
                order.sleeve,
            )

        if order.order_type == "LIMIT" and order.limit_px is not None:
            # BUY: fill if low <= limit; SELL: fill if high >= limit
            if order.side.upper() == "BUY" and bar.px_low <= order.limit_px:
                px = self._slip_px(order.limit_px, order.side)
                self.order_id += 1
                return FillEvent(
                    bar.ts,
                    order.symbol,
                    order.side,
                    order.qty,
                    px,
                    self.slip,
                    f"O{self.order_id}",
                    order.sleeve,
                )
            if order.side.upper() == "SELL" and bar.px_high >= order.limit_px:
                px = self._slip_px(order.limit_px, order.side)
                self.order_id += 1
                return FillEvent(
                    bar.ts,
                    order.symbol,
                    order.side,
                    order.qty,
                    px,
                    self.slip,
                    f"O{self.order_id}",
                    order.sleeve,
                )
        return None


# --------- Portfolio ---------
class Portfolio:
    def __init__(self, starting_cash=1_000_000.0):
        self.cash = float(starting_cash)
        self.pos = {}  # symbol -> qty (signed)
        self.avg_px = {}  # symbol -> avg fill px
        self.attrib = []  # list of dict rows (PnL per symbol/sleeve)
        self.equity = []  # time series of equity

    def on_fill(self, fill: FillEvent):
        sym, side, qty, px = (
            fill.symbol,
            fill.side.upper(),
            float(fill.qty),
            float(fill.px),
        )
        signed = +qty if side == "BUY" else -qty
        prev = self.pos.get(sym, 0.0)
        new = prev + signed

        # cash impact: fill price * qty + commission
        self.cash -= px * signed
        self.cash -= self._commission(qty)

        # avg price book-keeping
        if prev == 0.0 or np.sign(prev) == np.sign(new):
            # same direction or opening
            notional_prev = abs(prev) * self.avg_px.get(sym, px)
            notional_new = abs(signed) * px
            denom = abs(prev + signed)
            self.avg_px[sym] = (
                (notional_prev + notional_new) / denom if denom > 0 else px
            )
        else:
            # partial/flat close; avg_px remains for any residual
            if np.sign(new) != np.sign(prev) and new != 0.0:
                self.avg_px[sym] = px  # flipped; reset avg to last fill
            elif new == 0.0:
                self.avg_px.pop(sym, None)

        self.pos[sym] = new

        self.attrib.append(
            {
                "ts": fill.ts,
                "symbol": sym,
                "sleeve": fill.sleeve,
                "side": side,
                "qty": signed,
                "price": px,
                "commission": self._commission(qty),
                "slippage_bps": fill.slippage,
            }
        )

    def mark_to_market(self, ts: pd.Timestamp, last_px: Dict[str, float]):
        mtm = sum(self.pos.get(sym, 0.0) * last_px.get(sym, 0.0) for sym in last_px)
        eq = self.cash + mtm
        self.equity.append({"ts": ts, "equity": eq})

    def _commission(self, qty) -> float:
        return 0.0  # wire in if needed

    def to_frames(self):
        attrib = pd.DataFrame(self.attrib)
        equity = pd.DataFrame(self.equity)
        return attrib, equity


# --------- Orchestrator ---------
class BacktestEngine:
    def __init__(
        self, data: MarketData, broker: SimBroker, portfolio: Portfolio, strategy_fn
    ):
        """
        strategy_fn(bar, portfolio) -> list[OrderEvent]  (may be empty)
        """
        self.data = data
        self.broker = broker
        self.portfolio = portfolio
        self.strategy_fn = strategy_fn
        self.last_px = {}

    def run(self):
        for bar in self.data:
            self.last_px[bar.symbol] = bar.px_close

            # 1) Strategy generates orders
            orders = self.strategy_fn(bar, self.portfolio) or []

            # 2) Try fills
            for od in orders:
                fill = self.broker.try_fill(bar, od)
                if fill:
                    self.portfolio.on_fill(fill)

            # 3) Mark to market
            self.portfolio.mark_to_market(bar.ts, self.last_px)
