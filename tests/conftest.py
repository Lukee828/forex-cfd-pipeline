import tempfile
import shutil
import pytest

# tests/conftest.py
import importlib

CANDIDATE_FUNCS = (
    "detect_overbalance",
    "compute_ob",
    "overbalance_labels",
    "detect_swings",
)
CANDIDATE_MODULES = (
    "analytics.structure.ob",
    "analytics.structure.overbalance",
    "structure.ob",
    "structure.overbalance",
    "ob",
    "overbalance",
    "src.ob",
    "src.overbalance",
    "forex_cfd_pipeline.ob",
    "forex_cfd_pipeline.structure.overbalance",
)


def find_ob_func():
    for mod in CANDIDATE_MODULES:
        try:
            m = importlib.import_module(mod)
        except Exception:
            continue
        for name in CANDIDATE_FUNCS:
            f = getattr(m, name, None)
            if callable(f):
                return f
    return None


@pytest.fixture(autouse=True)
def _tmp_registry_dir(monkeypatch):
    d = tempfile.mkdtemp(prefix="registry_")
    # if your code reads something like REGISTRY_DB / ALPHA_DB / DUCKDB_PATH – adjust the name here:
    monkeypatch.setenv("ALPHA_REGISTRY_DIR", d)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
