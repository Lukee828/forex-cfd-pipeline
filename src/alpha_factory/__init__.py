# Re-export public API explicitly (satisfies Ruff F401)
from .base import (
    AlphaRegistry as AlphaRegistry,
    Factor as Factor,
    FactorSpec as FactorSpec,
)

__all__ = ["AlphaRegistry", "Factor", "FactorSpec"]

# Eagerly import factor modules so they self-register with the registry
from .factors import sma_cross  # noqa: F401
