from __future__ import annotations

import hashlib
import json
import os
import pickle
from pathlib import Path
from typing import Any, Iterable, Optional


def _normalize_key(key: Any) -> str:
    """
    Convert a user key into a deterministic JSON string (ASCII, sorted keys, no spaces).
    Ensures stable hashing → stable filenames for the same logical key.
    """
    return json.dumps(key, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _key_sha1(key: Any) -> str:
    return hashlib.sha1(_normalize_key(key).encode("ascii")).hexdigest()


class FeatureStore:
    """
    Minimal local feature store with atomic writes and deterministic file names.

    Layout:
      root/
        objects/<sha1>.pkl
    """

    def __init__(self, root: os.PathLike[str] | str):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)

    # --------- public API ---------

    def put(self, key: Any, value: Any, *, overwrite: bool = False) -> Path:
        """
        Persist value under key. If overwrite=False and object exists, raise FileExistsError.
        Returns the path to the stored object.
        """
        path = self._path_for_key(key)
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"Feature already exists for key={key!r} ({path.name})"
            )

        self._atomic_write(path, value)
        return path

    def get(self, key: Any) -> Any:
        path = self._path_for_key(key)
        with path.open("rb") as f:
            return pickle.load(f)

    def exists(self, key: Any) -> bool:
        return self._path_for_key(key).exists()

    def delete(self, key: Any) -> None:
        p = self._path_for_key(key)
        if p.exists():
            p.unlink()

    def list(self, prefix: Optional[str] = None) -> Iterable[str]:
        """
        List normalized keys we can recover from filenames: returns sha1 digests.
        (We don’t store reverse mapping; consumers compare by key→sha1.)
        If prefix is provided, filter digests starting with that prefix.
        """
        for p in sorted(self.objects.glob("*.pkl")):
            digest = p.stem
            if prefix is None or digest.startswith(prefix):
                yield digest

    # --------- internals ---------

    def _path_for_key(self, key: Any) -> Path:
        return self.objects / f"{_key_sha1(key)}.pkl"

    def _atomic_write(self, dst: Path, value: Any) -> None:
        """
        Write to a same-dir temporary file, then os.replace() → atomic on POSIX & Windows.
        Ensures no partial files are left on failure.
        """
        tmp = dst.with_suffix(".tmp." + os.urandom(4).hex())
        try:
            with tmp.open("wb") as f:
                # protocol 4 is widely compatible (3.4+), good enough for CI
                pickle.dump(value, f, protocol=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, dst)
        except Exception:
            # Best-effort cleanup if something fails before replace
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            raise
