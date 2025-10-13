from __future__ import annotations
from typing import Any, Tuple, Optional


def log_flag_states(flags: Any) -> None:
    """
    Print explicit flag states. Accepts anything with attributes matching names below.
    Safe: if attr missing, prints as 'n/a'.
    """
    names = [
        "vol_targeting",
        "cost_windows",
        "spread_guard",
        "dual_tp",
        "time_stop",
        "be_gate_opposite",
    ]
    parts = []
    for n in names:
        v = getattr(flags, n, "n/a")
        parts.append(f"{n}={v}")
    print("flags:", ", ".join(parts))


def extract_hints(
    ev: Any,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[int]]:
    """
    Return (price_hint, spread_hint, vol_hint, bar_index) using getattr to avoid schema breaks.
    Works with old SignalEvent objects that may not have these attributes.
    """
    price_hint = getattr(ev, "price_hint", None)
    spread_hint = getattr(ev, "spread_hint", None)
    vol_hint = getattr(ev, "vol_hint", None)
    bar_index = getattr(ev, "bar_index", None)
    return price_hint, spread_hint, vol_hint, bar_index


def maybe_manage_exits(
    portfolio: Any, symbol: str, current_px: float, bar_index: Optional[int]
) -> Optional[Any]:
    """
    If portfolio exposes manage_exits(sym, px, bar_index), call it; otherwise do nothing.
    This keeps wiring optional and schema-preserving.
    """
    fn = getattr(portfolio, "manage_exits", None)
    if callable(fn):
        return fn(symbol, current_px, bar_index=bar_index)
    return None
