from __future__ import annotations

import json
import hashlib

# Keep underscored aliases for the v2 helpers
import json as _json
import hashlib as _hashlib
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
            raise FileExistsError(f"Feature already exists for key={key!r} ({path.name})")

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


# ---- Legacy compatibility shims (legacy API surface) ----


# init(): ensure layout and return self
def _fs_compat_init(self):
    (self.objects).mkdir(parents=True, exist_ok=True)
    return self


FeatureStore.init = _fs_compat_init


# upsert_prices(): write under prices/<symbol> and return count
def _fs_compat_upsert_prices(self, symbol, df):
    self.put(f"prices/{symbol}", df, overwrite=True)
    try:
        return len(df)
    except Exception:
        return 0


FeatureStore.upsert_prices = _fs_compat_upsert_prices


# get_prices(): read what upsert_prices stored
def _fs_compat_get_prices(self, symbol):
    return self.get(f"prices/{symbol}")


FeatureStore.get_prices = _fs_compat_get_prices


# record_provenance(): no-op shim returning a dummy id
def _fs_compat_record_provenance(self, *args, **kwargs):
    return "prov-ignored"


FeatureStore.record_provenance = _fs_compat_record_provenance

# exists(): accept either (key) or (key, digestPath)
_FS_exists_orig = FeatureStore.exists


def _fs_compat_exists_dual(self, key, maybe_digest=None):
    from pathlib import Path as _P

    if maybe_digest is not None:
        return _P(maybe_digest).exists()
    return _FS_exists_orig(self, key)


FeatureStore.exists = _fs_compat_exists_dual

# get(): accept either (key) or (key, digestPath)
_FS_get_orig = FeatureStore.get


def _fs_compat_get_dual(self, key, maybe_digest=None):
    from pathlib import Path as _P
    import pickle as _pickle

    if maybe_digest is not None:
        with _P(maybe_digest).open("rb") as f:
            return _pickle.load(f)
    return _FS_get_orig(self, key)


FeatureStore.get = _fs_compat_get_dual

# ---- Compatibility: accept params/version/schema in put and mix into digest ----
try:
    import pandas as _pd
except Exception:
    _pd = None

_old_put = FeatureStore.put


def _fs_put_with_params(
    self, key, value, *, overwrite=False, params=None, version=None, schema=None
):
    meta = {"name": key}
    if params is not None:
        meta["params"] = params
    if version is not None:
        meta["version"] = version
    if schema is None and _pd is not None and hasattr(value, "dtypes"):
        meta["schema"] = [
            {"name": str(c), "dtype": str(value.dtypes[c])} for c in list(value.columns)
        ]
    elif schema is not None:
        meta["schema"] = schema
    path = self._path_for_key(meta)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Feature already exists for key={key!r} ({path.name})")
    self._atomic_write(path, value)
    return path


FeatureStore.put = _fs_put_with_params


# ---- Implement record_provenance(): return positive int id ----
def _fs_record_provenance(self, *args, **kwargs):
    import json as _json

    counter = self.root / "provenance.id"
    current = 0
    if counter.exists():
        try:
            current = int(counter.read_text().strip() or "0")
        except Exception:
            current = 0
    new = current + 1
    counter.write_text(str(new), encoding="utf-8")
    try:
        log = self.root / "provenance.log"
        with log.open("a", encoding="utf-8") as f:
            f.write(_json.dumps({"id": new, "args": list(args), "kwargs": kwargs}) + "\n")
    except Exception:
        pass
    return new


FeatureStore.record_provenance = _fs_record_provenance


# ---- Legacy pointers to reconcile rich meta digests with simple read keys ----
def _fs__ptr_dir(self):
    d = self.root / "pointers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fs__write_ptr(self, name, path):
    # name is the simple key (e.g., "prices/EURUSD"); path is Path to stored .pkl
    from pathlib import Path as _P

    ref = _fs__ptr_dir(self) / (_key_sha1(name) + ".ref")
    ref.write_text(_P(path).name, encoding="utf-8")


def _fs__read_ptr(self, name):
    ref = self.root / "pointers" / (_key_sha1(name) + ".ref")
    if ref.exists():
        return ref.read_text(encoding="utf-8").strip()
    return None


# Rewrap upsert_prices to write a pointer after storing
_old_upsert_prices = getattr(FeatureStore, "upsert_prices", None)


def _fs_compat_upsert_prices_v2(self, symbol, df):
    p = self.put(f"prices/{symbol}", df, overwrite=True)
    _fs__write_ptr(self, f"prices/{symbol}", p)
    try:
        return len(df)
    except Exception:
        return 0


FeatureStore.upsert_prices = _fs_compat_upsert_prices_v2

# Rewrap get_prices to use the pointer if present, else fall back
_old_get_prices = getattr(FeatureStore, "get_prices", None)


def _fs_compat_get_prices_v2(self, symbol):
    name = f"prices/{symbol}"
    digest = _fs__read_ptr(self, name)
    if digest:
        path = self.objects / digest
        with path.open("rb") as f:
            import pickle as _pickle

            return _pickle.load(f)
    # fallback: simple string key (if someone put without meta)
    return self.get(name)


FeatureStore.get_prices = _fs_compat_get_prices_v2


# ---- Finalize v2 API: direct, dual-signature get/exists ----
def _fs_get_final(self, key, maybe_digest=None):
    from pathlib import Path as _P
    import pickle as _pickle

    p = _P(maybe_digest) if maybe_digest is not None else self._path_for_key(key)
    with p.open("rb") as f:
        return _pickle.load(f)


FeatureStore.get = _fs_get_final


def _fs_exists_final(self, key, maybe_digest=None):
    from pathlib import Path as _P

    return (
        _P(maybe_digest).exists() if maybe_digest is not None else self._path_for_key(key).exists()
    )


FeatureStore.exists = _fs_exists_final


# ---- Canonical key normalization + digest (v2) ----


def _normalize_key_v2(key):
    # Strings pass through; everything else is normalized via JSON (stable ordering)
    if isinstance(key, str):
        return key
    return _json.dumps(key, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _key_sha1_v2(key):
    return _hashlib.sha1(_normalize_key_v2(key).encode("utf-8")).hexdigest()


# Export the canonical versions under the public helper names used by tests
_normalize_key = _normalize_key_v2
_key_sha1 = _key_sha1_v2


# Ensure the class uses the same mapping everywhere
def _path_for_key_v2(self, key):
    from pathlib import Path as _P

    return _P(self.objects) / f"{_key_sha1_v2(key)}.pkl"


FeatureStore._path_for_key = _path_for_key_v2


# Hard-override get/exists to rely on the same path function (still support legacy digest arg)
def _fs_get_final(self, key, maybe_digest=None):
    from pathlib import Path as _P
    import pickle as _pickle

    p = _P(maybe_digest) if maybe_digest is not None else self._path_for_key(key)
    with p.open("rb") as f:
        return _pickle.load(f)


FeatureStore.get = _fs_get_final


def _fs_exists_final(self, key, maybe_digest=None):
    from pathlib import Path as _P

    p = _P(maybe_digest) if maybe_digest is not None else self._path_for_key(key)
    return p.exists()


FeatureStore.exists = _fs_exists_final


# ---- Finalize put() to use canonical path mapping ----
def _fs_put_final(self, key, value, *, overwrite: bool = False):
    p = self._path_for_key(key)
    if p.exists() and not overwrite:
        raise FileExistsError(f"Feature already exists for key={key!r} ({p.name})")
    self._atomic_write(p, value)
    return p


FeatureStore.put = _fs_put_final


# ---- Accept params/schema/version; fold into canonical key ----
_FS_put_orig = FeatureStore.put


def _fs_put_with_params(
    self,
    name_or_key,
    value,
    *,
    params=None,
    schema=None,
    version=None,
    overwrite: bool = False,
):
    # Normalize: if user passed a plain name, promote to dict and attach metadata
    key = name_or_key
    if isinstance(name_or_key, (str, bytes)):
        key = {"name": name_or_key}
    # Attach optional dimensions so SHA changes when they change
    if params is not None:
        key["params"] = params
    if schema is not None:
        key["schema"] = schema
    if version is not None:
        key["version"] = version
    return _FS_put_orig(self, key, value, overwrite=overwrite)


FeatureStore.put = _fs_put_with_params


# ---- put(): accept params/schema/version without changing plain-key digests ----
_FS_put_orig = FeatureStore.put


def _fs_put_with_params(
    self,
    name_or_key,
    value,
    *,
    params=None,
    schema=None,
    version=None,
    overwrite: bool = False,
):
    # 1) If key is a plain string/bytes AND no extra metadata AND no schema inference is needed,
    #    pass through unchanged so the digest matches _key_sha1(plain_key).
    def _infer_schema_if_df(val):
        try:
            import pandas as _pd

            if isinstance(val, _pd.DataFrame):
                # Stable, order-preserving schema fingerprint: list of [name, dtype_str]
                return {"columns": [[str(c), str(val.dtypes[c])] for c in list(val.columns)]}
        except Exception:
            pass
        return None

    need_infer = (schema is None) and (_infer_schema_if_df(value) is not None)

    if (
        isinstance(name_or_key, (str, bytes))
        and params is None
        and schema is None
        and version is None
        and not need_infer
    ):
        return _FS_put_orig(self, name_or_key, value, overwrite=overwrite)

    # 2) Build a dict key when we have metadata or inferred schema.
    if isinstance(name_or_key, (str, bytes)):
        key = {"name": name_or_key}
    else:
        # Assume mapping-like key already; make a shallow copy to avoid mutating caller data
        try:
            key = dict(name_or_key)
        except Exception:
            # Fallback: embed as-is under "name"
            key = {"name": name_or_key}

    if params is not None:
        key["params"] = params
    if version is not None:
        key["version"] = version

    if schema is not None:
        key["schema"] = schema
    else:
        inferred = _infer_schema_if_df(value)
        if inferred is not None:
            key["schema"] = inferred

    return _FS_put_orig(self, key, value, overwrite=overwrite)


FeatureStore.put = _fs_put_with_params


# ---- idempotent, recursion-safe put() wrapper ----
# Capture the original once; subsequent executions won't re-wrap.
if not hasattr(FeatureStore, "_put_core"):
    FeatureStore._put_core = FeatureStore.put


def _fs_put_recursion_safe(
    self,
    name_or_key,
    value,
    *,
    params=None,
    schema=None,
    version=None,
    overwrite: bool = False,
):
    # Infer schema for DataFrame if not provided (so schema changes alter digest)
    def _infer_schema_if_df(val):
        try:
            import pandas as _pd

            if isinstance(val, _pd.DataFrame):
                return {"columns": [[str(c), str(val.dtypes[c])] for c in list(val.columns)]}
        except Exception:
            pass
        return None

    inferred = None
    if schema is None:
        inferred = _infer_schema_if_df(value)

    # Preserve digest for plain keys when no metadata & no inferred schema needed
    if (
        isinstance(name_or_key, (str, bytes))
        and params is None
        and schema is None
        and version is None
        and inferred is None
    ):
        return FeatureStore._put_core(self, name_or_key, value, overwrite=overwrite)

    # Build dict key (either from plain string or copy mapping)
    if isinstance(name_or_key, (str, bytes)):
        key = {"name": name_or_key}
    else:
        try:
            key = dict(name_or_key)
        except Exception:
            key = {"name": name_or_key}

    if params is not None:
        key["params"] = params
    if version is not None:
        key["version"] = version
    if schema is not None:
        key["schema"] = schema
    elif inferred is not None:
        key["schema"] = inferred

    return FeatureStore._put_core(self, key, value, overwrite=overwrite)


FeatureStore.put = _fs_put_recursion_safe


# ---- hard reset: recursion-proof put() ----
# A brand-new, never-wrapped core implementation.
def _fs__put_core_impl(self, key, value, *, overwrite: bool = False):
    p = self._path_for_key(key)
    if p.exists() and not overwrite:
        raise FileExistsError(f"Feature already exists for key={key!r} ({p.name})")
    self._atomic_write(p, value)
    return p


# Install/override the core every time to break any wrapper chains.
FeatureStore._put_core = _fs__put_core_impl


def _fs__infer_schema_if_df(val):
    try:
        import pandas as _pd

        if isinstance(val, _pd.DataFrame):
            return {"columns": [[str(c), str(val.dtypes[c])] for c in list(val.columns)]}
    except Exception:
        pass
    return None


def _fs__put_wrapper(
    self,
    name_or_key,
    value,
    *,
    params=None,
    schema=None,
    version=None,
    overwrite: bool = False,
):
    inferred = None if schema is not None else _fs__infer_schema_if_df(value)

    # Preserve digest for plain keys when no metadata and no inferred schema.
    if (
        isinstance(name_or_key, (str, bytes))
        and params is None
        and schema is None
        and version is None
        and inferred is None
    ):
        return self._put_core(name_or_key, value, overwrite=overwrite)

    # Build dict key
    if isinstance(name_or_key, (str, bytes)):
        key = {"name": name_or_key}
    else:
        try:
            key = dict(name_or_key)
        except Exception:
            key = {"name": name_or_key}

    if params is not None:
        key["params"] = params
    if version is not None:
        key["version"] = version
    if schema is not None:
        key["schema"] = schema
    elif inferred is not None:
        key["schema"] = inferred

    return self._put_core(key, value, overwrite=overwrite)


# Point public API to the wrapper that always calls the true core.
FeatureStore.put = _fs__put_wrapper


# ---- refine put(): preserve non-string keys unless metadata present ----
def _fs__infer_schema_if_df(val):
    try:
        import pandas as _pd

        if isinstance(val, _pd.DataFrame):
            return {"columns": [[str(c), str(val.dtypes[c])] for c in list(val.columns)]}
    except Exception:
        pass
    return None


def _fs__put_wrapper_v2(
    self,
    name_or_key,
    value,
    *,
    params=None,
    schema=None,
    version=None,
    overwrite: bool = False,
):
    # Fast path: plain str key + no metadata → identical digest behavior
    inferred = None if schema is not None else _fs__infer_schema_if_df(value)
    if (
        isinstance(name_or_key, (str, bytes))
        and params is None
        and schema is None
        and version is None
        and inferred is None
    ):
        return self._put_core(name_or_key, value, overwrite=overwrite)

    # Decide final key
    if params is None and schema is None and version is None and inferred is None:
        # No metadata: leave non-string keys (e.g., tuples) as-is to keep stable digest
        key = name_or_key
    else:
        # Need metadata: ensure a dict key
        if isinstance(name_or_key, dict):
            key = dict(name_or_key)  # shallow copy
        elif isinstance(name_or_key, (str, bytes)):
            key = {"name": name_or_key}
        else:
            key = {"name": name_or_key}
        if params is not None:
            key["params"] = params
        if version is not None:
            key["version"] = version
        if schema is not None:
            key["schema"] = schema
        elif inferred is not None:
            key["schema"] = inferred

    return self._put_core(key, value, overwrite=overwrite)


FeatureStore.put = _fs__put_wrapper_v2
