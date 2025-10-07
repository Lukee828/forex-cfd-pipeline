from .base import (
    AlphaRegistry as AlphaRegistry,
    Factor as Factor,
    FactorSpec as FactorSpec,
    registry as registry,
)

__all__ = ["AlphaRegistry", "Factor", "FactorSpec", "registry"]
# Eagerly import factor modules so they self-register with the registry
from .factors import sma_cross  # noqa: F401
from .factors import sma_slope  # noqa: F401
from .factors import rsi_thresh  # noqa: F401
