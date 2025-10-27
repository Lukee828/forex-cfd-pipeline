from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def test_smoke_allocation_stable():
    cfg = AllocatorConfig(
        mode="ewma", ewma_alpha=0.5, turnover_penalty=0.05, corr_cap=0.6, corr_governor_strength=0.5
    )
    alloc = MetaAllocator(cfg)
    metrics = {
        "TF": {"sharpe": 1.2, "dd": 0.06},
        "MR": {"sharpe": 1.0, "dd": 0.04},
        "VOL": {"sharpe": 0.6, "dd": 0.03},
    }
    prev = {"TF": 0.4, "MR": 0.4, "VOL": 0.2}
    corr = {("TF", "MR"): 0.7, ("MR", "VOL"): 0.2, ("TF", "VOL"): 0.3}
    w = alloc.allocate(metrics, prev_weights=prev, corr=corr)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    for k in ("TF", "MR", "VOL"):
        assert 0.0 <= w[k] <= 1.0
