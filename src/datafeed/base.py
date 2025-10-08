from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable
import pandas as pd


@dataclass(frozen=True)
class PriceBar:
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class PriceSource(Protocol):
    def fetch(
        self, symbol: str, *, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame: ...


def to_df(rows: Iterable[PriceBar]) -> pd.DataFrame:
    df = pd.DataFrame([r.__dict__ for r in rows])
    df = df.set_index(pd.to_datetime(df.pop("ts")))
    return df.sort_index()
