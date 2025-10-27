from .meta_allocator import MetaAllocator, AllocatorConfig
from .registry import make, names
from . import registry as registry  # re-export module for tests expecting `alpha_factory.registry`

__all__ = [
    "MetaAllocator",
    "AllocatorConfig",
    "make",
    "names",
    "registry",
]
