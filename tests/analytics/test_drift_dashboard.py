import numpy as np
import pandas as pd
from zigzagob.alpha_factory.drift_dashboard import (
    compute_tabular_drift,
    population_stability_index,
    rolling_stats,
    simple_html_report,
)


def test_psi_detects_shift():
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(0.0, 1.0, 5000))
    cur = pd.Series(rng.normal(0.3, 1.2, 5000))
    psi = population_stability_index(ref, cur, bins=10)
    assert psi > 0.1  # noticeable drift


def test_tabular_drift_and_html(tmp_path):
    rng = np.random.default_rng(1)
    ref = pd.DataFrame(
        {
            "feat1": rng.normal(0.0, 1.0, 2000),
            "feat2": rng.normal(0.0, 2.0, 2000),
        }
    )
    cur = pd.DataFrame(
        {
            "feat1": rng.normal(0.5, 1.0, 2000),  # mean shift
            "feat2": rng.normal(0.0, 1.0, 2000),  # variance shrink
        }
    )
    m = compute_tabular_drift(ref, cur, bins=10)
    assert set(m.columns) >= {
        "column",
        "psi",
        "mean_ref",
        "mean_cur",
        "delta_mean",
        "std_ref",
        "std_cur",
        "std_ratio",
        "n_ref",
        "n_cur",
    }
    # Check our intended drifts appear sensibly ranked
    assert (m.loc[m["column"] == "feat1", "delta_mean"].abs().iloc[0]) > 0.3
    assert (m.loc[m["column"] == "feat2", "std_ratio"].iloc[0]) < 1.0

    # HTML export writes a file
    out = tmp_path / "report.html"
    html = simple_html_report(m, title="Drift Report", path=str(out))
    assert out.exists() and "Drift Report" in html


def test_rolling_stats_shapes():
    s = pd.Series(np.arange(100, dtype=float))
    r = rolling_stats(s, window=20)
    assert list(r.columns) == ["roll_mean", "roll_std"]
    assert len(r) == 100
