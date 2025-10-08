from __future__ import annotations
import os

# Environment switches (case-insensitive):
#   FEATURE_ENGINE = pandas | polars
#   ROLL_IMPL      = numpy  | numba
#   BACKTEST_EXECUTOR = serial | process | ray  (suggested; wired later)


def _env(name: str, default: str) -> str:
    val = os.environ.get(name, default)
    return (val or default).strip().lower()


def feature_engine() -> str:
    it = _env("FEATURE_ENGINE", "pandas")
    return "polars" if it == "polars" else "pandas"


def roll_impl() -> str:
    it = _env("ROLL_IMPL", "numpy")
    return "numba" if it == "numba" else "numpy"


def backtest_executor() -> str:
    it = _env("BACKTEST_EXECUTOR", "serial")
    return it if it in {"serial", "process", "ray"} else "serial"
