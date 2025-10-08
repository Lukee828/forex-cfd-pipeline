from src.alpha_factory import registry


def test_registry_has_examples():
    names = set(registry.names())
    expected = {"sma_cross_10_30", "sma_slope_20_1", "rsi_thresh_14_30_70"}
    missing = expected - names
    assert not missing, f"Missing expected factors: {missing}"
