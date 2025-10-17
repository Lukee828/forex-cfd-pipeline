from __future__ import annotations
import os, os.path as op

RUN_LEGACY = os.getenv("RUN_LEGACY_TESTS", "0") == "1"

def _is_legacy(path: str) -> bool:
    p = path.replace("\\", "/")
    if "/tests/alpha_factory/" in p:
        return True
    if "/tests/registry/" in p:
        return True
    if p.endswith("/tests/test_ob_logic.py"):
        return True
    return False

def pytest_ignore_collect(path, config):
    # Block collection (and thus imports) of legacy suites unless explicitly enabled
    if RUN_LEGACY:
        return False
    return _is_legacy(str(path))