from __future__ import annotations
import importlib as _il

# load the real module that lives under src/
_m = _il.import_module("src.alpha_factory.registry_tooling_v027")

# re-export (public API)
globals().update({k: getattr(_m, k) for k in dir(_m) if not k.startswith("_")})

# be explicit about key names tests expect
alerts = getattr(_m, "alerts", None)
RegistryCLI = getattr(_m, "RegistryCLI", None)

__all__ = [k for k in globals() if not k.startswith("_")]
