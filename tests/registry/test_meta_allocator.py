import numpy as np
import pandas as pd

from zigzagob.alpha_factory.meta_allocator import MetaAllocator, EWMAConfig, BayesConfig


def _make_returns(n=300, seed=42):
    rng = np.random.default_rng(seed)
    a = rng.normal(0.0006, 0.01, n)  # sleeve A: better mean
    b = rng.normal(0.0001, 0.01, n)  # sleeve B: worse mean
    c = rng.normal(0.0004, 0.015, n)  # sleeve C: mid mean, higher vol
    idx = pd.RangeIndex(n)
    return pd.DataFrame({"A": a, "B": b, "C": c}, index=idx)


def test_ewma_allocator_prefers_better_sleeve():
    rets = _make_returns()
    alloc = MetaAllocator(mode="ewma", ewma_cfg=EWMAConfig(decay=0.95, temperature=0.8))
    W = alloc.allocate(rets)
    # weights sum to 1
    assert np.allclose(W.sum(axis=1).values, 1.0, atol=1e-8)
    # avg weight on A (best mean) should exceed B
    assert W["A"].mean() > W["B"].mean()


def test_bayes_allocator_prefers_better_sleeve():
    rets = _make_returns(seed=7)
    alloc = MetaAllocator(mode="bayes", bayes_cfg=BayesConfig(window=50, temperature=0.9))
    W = alloc.allocate(rets)
    assert np.allclose(W.sum(axis=1).values, 1.0, atol=1e-8)
    assert W["A"].mean() > W["B"].mean()
