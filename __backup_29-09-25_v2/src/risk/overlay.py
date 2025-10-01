from typing import List
from ..sleeves.base import OrderIntent


def apply_caps(
    order_intents: List[OrderIntent],
    equity: float,
    inst_cap=0.08,
    corr_guard=0.6,
    mtd_limits=(-0.06, -0.10),
    sleeve_weights: dict | None = None,
) -> List[OrderIntent]:
    # Placeholder: only pass-through and annotate confidence by sleeve weight
    if sleeve_weights is None:
        return order_intents
    out = []
    for oi in order_intents:
        mult = sleeve_weights.get(oi.tag, 1.0)
        out.append(
            OrderIntent(
                oi.ts_utc,
                oi.symbol,
                oi.side,
                oi.entry,
                oi.exit,
                oi.tag,
                oi.priority,
                oi.confidence * mult,
            )
        )
    return out
