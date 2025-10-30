import numpy as np
from alpha_factory.regime_hazard import RegimeHazard, RegimeHazardState


def test_hazard_detects_spike_and_persists(tmp_path):
    # mostly chill regime
    base = np.random.normal(loc=1.0, scale=0.05, size=200)
    # huge shock
    series = np.copy(base)
    series[-1] = 1.5  # ~10 std jumps relative to base ~0.05 std

    h = RegimeHazard(threshold=2.0)
    state = h.update_from_vol_series(series)

    assert isinstance(state, RegimeHazardState)
    assert state.score > 2.0
    assert state.hazard is True
    assert state.reason == "vol_spike"

    outdir = tmp_path / "regime"
    outdir.mkdir()
    latest = h.save_status(outdir)
    assert latest.exists()

    # reload into new process style
    reloaded = RegimeHazard.load_latest(outdir)
    assert reloaded.hazard is True
    assert reloaded.reason == "vol_spike"
    assert reloaded.score >= state.score * 0.9
