from __future__ import annotations
from src.runtime.governor_integration import governor_scale
s, info = governor_scale(100.0, 100_000.0)
print("scale=", round(s,6), "mode=", info.get("mode"), "dd_tripped=", info.get("dd_tripped"), "vol_ann=", info.get("vol_ann"))