from typing import Any, Optional

# Try to import real symbols, but keep file import-safe in all envs
try:
    from src.risk.spread_guard import SpreadGuardConfig  # type: ignore
except Exception:  # pragma: no cover
    SpreadGuardConfig = None  # type: ignore[misc]

def new_spread_guard_config(**kwargs: Any) -> Optional[Any]:
    """
    Create a SpreadGuardConfig regardless of the constructor kw name.
    Tries common variants: max_spread_bps, max_bps, limit_bps, max_spread.
    Returns None if SpreadGuardConfig is unavailable.
    """
    if SpreadGuardConfig is None:
        return None

    candidates = (
        "max_spread_bps",
        "max_bps",
        "limit_bps",
        "max_spread",
    )
    # If caller passed a numeric without a key, normalize it to expected kw
    if len(kwargs) == 1 and next(iter(kwargs.values())).__class__ in (int, float):
        val = next(iter(kwargs.values()))
        kwargs = {}  # reset into proper kw below
        # fall through to inject as first candidate

    for key in candidates:
        try:
            if "val" in locals():
                return SpreadGuardConfig(**{key: val})
            if key in kwargs:
                return SpreadGuardConfig(**{key: kwargs[key]})
        except TypeError:
            # wrong kw; try next
            pass

    # Last attempt: pass through raw kwargs (might be positional in upstream)
    try:
        return SpreadGuardConfig(**kwargs)  # type: ignore[arg-type]
    except Exception:
        return None