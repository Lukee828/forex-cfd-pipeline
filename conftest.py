from __future__ import annotations
import os, pytest

# Skip legacy suites by default. Re-enable with: RUN_LEGACY_TESTS=1
RUN_LEGACY = os.getenv("RUN_LEGACY_TESTS","0") == "1"

def pytest_collection_modifyitems(config, items):
    if RUN_LEGACY:
        return
    skip = pytest.mark.skip(reason="Skipping legacy alpha_factory/registry/ob_logic until wired into current infra.")
    for item in items:
        p = str(item.fspath).replace("\\\\","/")
        if ("/tests/alpha_factory/" in p) or ("/tests/registry/" in p) or p.endswith("/tests/test_ob_logic.py"):
            item.add_marker(skip)

