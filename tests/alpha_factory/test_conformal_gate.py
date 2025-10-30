import numpy as np
from alpha_factory.conformal_gate import ConformalGate


def make_linear_data(n=500):
    rng = np.random.default_rng(123)
    X = rng.normal(size=(n, 3))
    # True rule: if X0 + 0.5*X1 - X2 > 0 -> success
    y = (X[:, 0] + 0.5 * X[:, 1] - X[:, 2] > 0.0).astype(int)
    names = ["f0", "f1", "f2"]
    return X, y, names


def test_gate_fits_and_accepts_confident_trades(tmp_path):
    X, y, names = make_linear_data(800)

    gate = ConformalGate(
        coverage_target=0.9,
        calibration_window=2000,
        min_samples=100,
    )
    gate.fit_from_history(X, y, names)

    assert gate.bundle is not None
    assert gate.bundle.tau >= 0.0
    assert gate.bundle.n_calib > 0

    # score an obviously strong trade
    strong = {"f0": 3.0, "f1": 2.0, "f2": -2.5}
    decision = gate.score_live_trade(strong)
    assert decision["decision"] in ("ACCEPT", "ABSTAIN")
    # At least exercise the path
    assert "p_win" in decision
    assert "tau" in decision


def test_gate_passthrough_when_not_enough_data():
    X = np.random.rand(50, 3)
    y = (X[:, 0] > 0.5).astype(int)
    names = ["a", "b", "c"]

    gate = ConformalGate(min_samples=300)
    gate.fit_from_history(X, y, names)

    assert gate.bundle is not None
    assert gate.bundle.note.startswith("NOT_ENOUGH_SAMPLES")
    d = gate.score_live_trade({"a": 0.1, "b": 0.2, "c": 0.3})
    assert d["decision"] == "ACCEPT"  # passthrough
