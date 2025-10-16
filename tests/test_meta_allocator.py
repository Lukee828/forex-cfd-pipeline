from __future__ import annotations
import pandas as pd
from src.infra.meta_allocator import MetaAllocator, MetaAllocatorConfig

def test_basic_sharpe_only():
    df = pd.DataFrame({"sharpe":[1.0, 0.5, 0.0]}, index=["A","B","C"])
    w = MetaAllocator().compute_weights(df)
    assert abs(w["A"] - 2/3) < 1e-6
    assert abs(w["B"] - 1/3) < 1e-6
    assert w.get("C",0.0) <= 1e-12

def test_with_dd_penalty():
    cfg = MetaAllocatorConfig(include_dd=True)
    df = pd.DataFrame({"sharpe":[1.0, 1.0], "dd":[0.0, 0.5]}, index=["A","B"])
    w = MetaAllocator(cfg).compute_weights(df)
    assert w["A"] > w["B"] and abs(w.sum()-1.0) < 1e-9

def test_with_risk_scale():
    df = pd.DataFrame({"sharpe":[1.0, 1.0]}, index=["A","B"])
    rs = {"A":1.0, "B":0.2}
    w = MetaAllocator().compute_weights(df, risk_scale=rs)
    assert w["A"] > w["B"] and abs(w.sum()-1.0) < 1e-9
