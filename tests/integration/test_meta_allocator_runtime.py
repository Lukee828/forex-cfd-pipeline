from __future__ import annotations
import pandas as pd
from src.infra.meta_allocator import MetaAllocator, MetaAllocatorConfig

def test_meta_allocator_runtime_with_scales():
    cfg = MetaAllocatorConfig(include_dd=True, include_vol=False)
    alloc = MetaAllocator(cfg)
    # pretend sleeves
    rows = pd.DataFrame({
        "sharpe":[1.2, 0.8, 0.3],
        "dd":[0.10, 0.05, 0.20],
    }, index=["ZZ","S2E","MR"])
    # suppose governor throttles MR (e.g., 0.4) and leaves ZZ,S2E at ~1
    rs = {"ZZ":1.0, "S2E":0.9, "MR":0.4}
    w = alloc.compute_weights(rows, risk_scale=rs)
    assert set(w.index) == {"ZZ","S2E","MR"}
    assert abs(w.sum()-1.0) < 1e-9
    assert w["ZZ"] > w["MR"]
