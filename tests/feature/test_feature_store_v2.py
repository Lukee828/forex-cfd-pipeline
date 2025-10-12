import pickle
import tempfile
from pathlib import Path

import pytest

from feature.feature_store import FeatureStore, _key_sha1


@pytest.fixture()
def fs_tmp():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_put_get_roundtrip(fs_tmp):
    fs = FeatureStore(fs_tmp)
    key = {"pair": "EURUSD", "tf": "H1", "from": "2023-01-01", "to": "2023-02-01"}
    value = {"n": 3, "arr": [1, 2, 3]}
    p = fs.put(key, value)
    assert p.exists()
    got = fs.get(key)
    assert got == value
    # path is deterministic for same key
    assert p.name == f"{_key_sha1(key)}.pkl"


def test_put_collision_requires_overwrite(fs_tmp):
    fs = FeatureStore(fs_tmp)
    key = "alpha/A"
    fs.put(key, 1)
    with pytest.raises(FileExistsError):
        fs.put(key, 2, overwrite=False)
    fs.put(key, 2, overwrite=True)
    assert fs.get(key) == 2


def test_exists_delete(fs_tmp):
    fs = FeatureStore(fs_tmp)
    key = ("beta", 42)
    assert not fs.exists(key)
    fs.put(key, {"ok": True})
    assert fs.exists(key)
    fs.delete(key)
    assert not fs.exists(key)


def test_list_prefix_filters(fs_tmp):
    fs = FeatureStore(fs_tmp)
    k1 = "alpha/A"
    k2 = "alpha/B"
    k3 = "beta/C"
    fs.put(k1, 1)
    fs.put(k2, 2)
    fs.put(k3, 3)
    all_digests = list(fs.list())
    assert set(all_digests) == {_key_sha1(k1), _key_sha1(k2), _key_sha1(k3)}
    only_a = list(fs.list(prefix=_key_sha1(k1)[:2]))
    assert _key_sha1(k1) in only_a


def test_atomic_write_no_partial_on_failure(fs_tmp, monkeypatch):
    """
    If serialization fails, temp file should be cleaned; final file must not exist.
    """
    fs = FeatureStore(fs_tmp)
    key = "boom"

    # Spy into tmp path creation by wrapping _atomic_write's pickle.dump
    def boom_dump(*args, **kwargs):
        raise RuntimeError("serialize fail")

    monkeypatch.setattr(pickle, "dump", boom_dump)

    with pytest.raises(RuntimeError):
        fs.put(key, {"x": 1})

    # Ensure no final file, and no lingering *.tmp files
    dst = fs_tmp / "objects" / f"{_key_sha1(key)}.pkl"
    assert not dst.exists()
    tmps = list((fs_tmp / "objects").glob("*.tmp.*"))
    assert not tmps
