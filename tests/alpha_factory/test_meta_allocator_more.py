from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def test_bayes_mode_normalizes():
    m = {"A": {"sharpe": 0.2, "dd": 0.10}, "B": {"sharpe": 0.0, "dd": 0.05}}
    w = MetaAllocator(AllocatorConfig(mode="bayes")).allocate(m)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert set(w) == {"A", "B"}


def test_empty_metrics_returns_empty():
    w = MetaAllocator().allocate({})
    assert w == {}
