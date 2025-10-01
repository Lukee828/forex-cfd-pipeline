from abc import ABC, abstractmethod
from typing import List
from .events import MarketEvent, SignalEvent


class Strategy(ABC):
    @abstractmethod
    def on_market(self, ev: MarketEvent) -> List[SignalEvent]: ...
