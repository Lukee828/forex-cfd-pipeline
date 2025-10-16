from __future__ import annotations
from pathlib import Path
import os
from .feature_store import FeatureStore

DEFAULT_DB = os.getenv("FEATURE_DB", "data/feature_store.duckdb")

TABLES = {
    "ticks": "ticks",
    "risk_snapshots": "risk_snapshots",
}

def get_store(db_path: str | None = None) -> FeatureStore:
    """
    Central place to obtain the FeatureStore. Uses FEATURE_DB if set.
    Keeps the codebase from hardcoding paths/tables everywhere.
    """
    return FeatureStore(db_path or DEFAULT_DB)