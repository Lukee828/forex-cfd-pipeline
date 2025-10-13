"""
AlphaRegistry v0.2.4 extensions — loader only.

This module intentionally does not define analytics itself. It just imports
the DuckDB-safe overrides which monkey-patch AlphaRegistry on import.
"""

from __future__ import annotations

# Ensure the base class is importable
from alpha_factory.alpha_registry import AlphaRegistry  # noqa: F401

# Install v0.2.4 overrides (JSON-safe, no self.con dependency, auto 'runs' view)
import alpha_factory.alpha_registry_ext_overrides_024  # noqa: F401
