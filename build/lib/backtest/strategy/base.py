from abc import ABC, abstractmethod
from typing import List
import pandas as pd

from ..events import SignalEvent  # re-export type hints if you wish


class Strategy(ABC):
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = list(symbols)

    @abstractmethod
    def on_bar(self, prices: pd.DataFrame, step: int) -> List[SignalEvent]:
        """
        Called once per step by the engine.
        prices: DataFrame of closes [ts x symbol], containing at least up to `step`.
        step:   Zero-based index of the current bar (row in `prices`).
        Return: A list of SignalEvent for this bar.
        """
        ...
