from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable, Dict, Callable
import pandas as pd


class Factor(Protocol):
    name: str
    requires: Iterable[str]

    def compute(self, df: pd.DataFrame) -> pd.Series: ...


@dataclass
class FactorSpec:
    name: str
    factory: Callable[[], Factor]


class AlphaRegistry:
    _factors: Dict[str, FactorSpec] = {}

    @classmethod
    def register(cls, spec: FactorSpec) -> None:
        if spec.name in cls._factors:
            raise ValueError(f"factor '{spec.name}' already registered")
        cls._factors[spec.name] = spec

    @classmethod
    def make(cls, name: str) -> Factor:
        try:
            return cls._factors[name].factory()
        except KeyError:
            raise KeyError(f"unknown factor '{name}'") from None

    @classmethod
    def names(cls) -> list[str]:
        return sorted(cls._factors.keys())


__all__ = (
    "AlphaRegistry",
    "Factor",
    "FactorSpec",
    "registry",
)
# --- Global registry singleton (available to factor modules) ---
try:
    registry  # type: ignore[name-defined]
except NameError:
    registry = AlphaRegistry()
