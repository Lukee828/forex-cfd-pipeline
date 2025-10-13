from typing import List
from ..sleeves.base import OrderIntent


def to_net(intents: List[OrderIntent]) -> List[OrderIntent]:
    # Sort by time then priority desc; keep last per (ts,symbol)
    intents = sorted(intents, key=lambda x: (x.ts_utc, -x.priority))
    out = []
    seen = set()
    for oi in intents:
        key = (oi.ts_utc, oi.symbol)
        if key in seen:
            continue
        out.append(oi)
        seen.add(key)
    return out
