import datetime
from dataclasses import dataclass
from typing import Dict, Literal

EventType = Literal["MARKET", "SIGNAL", "ORDER", "FILL"]


@dataclass(frozen=True)
class MarketEvent:
    type: EventType = "MARKET"
    ts: datetime.datetime = None
    ohlcv_by_sym: Dict[str, Dict[str, float]] = None  # { "EURUSD": {"Open":..., "Close":...}, ... }


@dataclass(frozen=True)
class SignalEvent:
    type: EventType = "SIGNAL"
    ts: datetime.datetime = None
    symbol: str = ""
    direction: Literal["LONG", "SHORT", "FLAT"] = "FLAT"
    strength: float = 1.0  # fraction of target position (simple for now)


@dataclass(frozen=True)
class OrderEvent:
    type: EventType = "ORDER"
    ts: datetime.datetime = None
    symbol: str = ""
    side: Literal["BUY", "SELL", "FLAT"] = "FLAT"
    qty: float = 0.0  # units/shares; for FX you can treat as notional lots later


@dataclass(frozen=True)
class FillEvent:
    type: EventType = "FILL"
    ts: datetime.datetime = None
    symbol: str = ""
    side: Literal["BUY", "SELL"] = "BUY"
    qty: float = 0.0
    price: float = 0.0
    commission: float = 0.0
