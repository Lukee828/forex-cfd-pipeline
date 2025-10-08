from __future__ import annotations
from typing import Any
from src.runtime.switches import feature_engine


def have_polars() -> bool:
    try:
        import polars as _  # noqa: F401

        return True
    except Exception:
        return False


def engine_name() -> str:
    eng = feature_engine()
    return "polars" if (eng == "polars" and have_polars()) else "pandas"


def read_parquet(path: str):
    if engine_name() == "polars":
        import polars as pl

        return pl.read_parquet(path)
    else:
        import pandas as pd

        return pd.read_parquet(path)


def to_pandas(df: Any):
    # Normalize to pandas when needed
    try:
        import polars as pl

        if isinstance(df, pl.DataFrame):
            return df.to_pandas()
    except Exception:
        pass
    return df
