from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def test_contract_weights_in_range_and_sum_to_1():
    cfg = AllocatorConfig()
    m = MetaAllocator(cfg)
    metrics = {
        "A": {"sharpe": 1.0, "dd": 0.05},
        "B": {"sharpe": 0.8, "dd": 0.03},
        "C": {"sharpe": 0.5, "dd": 0.04},
    }
    prev = {"A": 0.3, "B": 0.4, "C": 0.3}
    corr = {("A", "B"): 0.7, ("B", "C"): 0.5, ("A", "C"): 0.2}
    w = m.allocate(metrics, prev_weights=prev, corr=corr)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    for k, v in w.items():
        assert 0.0 <= v <= 1.0
