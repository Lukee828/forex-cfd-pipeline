"""
Legacy v0.2.4 AlphaRegistry overrides — safe no-op shim.
Importing sets INSTALLED=True for tests that expect side effects.
"""
from __future__ import annotations
INSTALLED = False
def install() -> bool:
    global INSTALLED
    INSTALLED = True
    return True
# Side-effect on import
install()
apply = install
__all__ = ["install", "apply", "INSTALLED"]
