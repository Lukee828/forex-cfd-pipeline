from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def test_meta_allocator_smoke():
    metrics = {
        "TF": {"sharpe": 1.2, "dd": 0.06},
        "MR": {"sharpe": 1.0, "dd": 0.05},
        "VOL": {"sharpe": 0.8, "dd": 0.04},
    }
    w = MetaAllocator(AllocatorConfig(mode="ewma")).allocate(metrics)
    assert set(w) == {"TF", "MR", "VOL"}
    assert abs(sum(w.values()) - 1.0) < 1e-9
