from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class FeatureKey:
    name: str
    version: str
    params_hash: str
    schema_hash: str

    def as_str(self) -> str:
        return (
            f"{self.name}-{self.version}-{self.params_hash[:8]}-{self.schema_hash[:8]}"
        )


def _stable_hash(obj: Any) -> str:
    """Hash Python obj via canonical JSON (sorted keys, no whitespace)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _schema_signature(df: pd.DataFrame) -> Dict[str, str]:
    # map column -> dtype.name (string)
    return {str(c): str(df.dtypes[c].name) for c in df.columns}


class FeatureStore:
    """
    Minimal local feature store (pickle backend) to unblock tests.
    Writes to `.fs/<name>/<key>.pkl`. Next PRs: DuckDB + provenance.
    """

    def __init__(self, root: Path | str = ".fs"):
        self.root = Path(root)

    def _key_for(
        self,
        name: str,
        df: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None,
        version: str = "v1",
    ) -> FeatureKey:
        params = params or {}
        p_hash = _stable_hash({"name": name, "version": version, "params": params})
        s_hash = _stable_hash(_schema_signature(df))
        return FeatureKey(
            name=name, version=version, params_hash=p_hash, schema_hash=s_hash
        )

    def _path_for(self, fk: FeatureKey) -> Path:
        return self.root / fk.name / f"{fk.as_str()}.pkl"

    def put(
        self,
        name: str,
        df: pd.DataFrame,
        *,
        params: Optional[Dict[str, Any]] = None,
        version: str = "v1",
    ) -> str:
        fk = self._key_for(name, df, params=params, version=version)
        path = self._path_for(fk)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Pickle keeps index/types; lightweight for now
        df.to_pickle(path)
        return fk.as_str()

    def get(self, name: str, key: str) -> pd.DataFrame:
        path = self.root / name / f"{key}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"No artifact for {name=} {key=}")
        return pd.read_pickle(path)

    def exists(self, name: str, key: str) -> bool:
        return (self.root / name / f"{key}.pkl").exists()
