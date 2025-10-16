from __future__ import annotations
from src.qa.regression_suite import run_case, Case

def test_run_case_sanity():
    c = Case("SMALL", [100, 101, 99, 100, 102], 100_000.0)
    r = run_case(c)
    assert r.name == "SMALL"
    assert r.final_equity > 0
    assert 0.0 <= r.max_dd <= 1.0
    assert 0.0 <= r.mean_scale <= 2.0
