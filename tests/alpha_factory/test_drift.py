from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

from alpha_factory.drift import (
    record_snapshot,
    load_history,
    compute_drift_metrics,
    render_html_report,
)
from alpha_factory.alloc_io import Allocation


def _fake_targets_csv(path: Path, gross: float = 0.75) -> None:
    """
    Create a tiny targets CSV like artifacts/targets/latest.csv:
    index is timestamp, columns are assets, values are exposures.
    We'll make a single-row file where row.abs().sum() == gross.
    """
    idx = ["2024-01-01T00:00:00Z"]
    df = pd.DataFrame(
        [[gross / 3.0, gross / 3.0, gross / 3.0]],
        index=idx,
        columns=["EURUSD", "GBPUSD", "USDJPY"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=True)


def test_drift_pipeline_end_to_end(tmp_path: Path) -> None:
    """
    Simulates what cli_drift.py would do:
    - write a few snapshots into history
    - load history
    - compute drift metrics
    - render HTML
    - assert shapes / sanity
    """

    hist_path = tmp_path / "drift_history.csv"
    outdir = tmp_path / "drift"
    targets_path = tmp_path / "targets_latest.csv"

    # 1) create a fake targets CSV with gross exposure ~0.75
    _fake_targets_csv(targets_path, gross=0.75)

    # 2) pretend we had allocator weights from previous days
    # sleeve weights look like TF/MR/VOL allocations that sum to ~1
    snapshots = [
        (datetime.utcnow() - timedelta(days=2), {"TF": 0.5, "MR": 0.3, "VOL": 0.2}, 0.60),
        (datetime.utcnow() - timedelta(days=1), {"TF": 0.55, "MR": 0.25, "VOL": 0.20}, 0.65),
        (datetime.utcnow(), {"TF": 0.52, "MR": 0.28, "VOL": 0.20}, 0.70),
    ]

    for ts, weights, gross_expo in snapshots:
        record_snapshot(
            history_path=hist_path,
            timestamp=ts,
            sleeve_weights=weights,
            gross_exposure=gross_expo,
        )

    # 3) load history back
    hist_df = load_history(hist_path)
    assert not hist_df.empty
    assert set(["ts", "gross"]).issubset(hist_df.columns)
    # should have TF/MR/VOL columns from our snapshots
    for k in ["TF", "MR", "VOL"]:
        assert k in hist_df.columns

    # 4) compute drift stats over last N points
    metrics_df = compute_drift_metrics(hist_df, lookback=10)
    # Expect rows for TF, MR, VOL, gross
    for key in ["TF", "MR", "VOL", "gross"]:
        assert (metrics_df["name"] == key).any(), f"{key} missing in metrics_df"

    # required columns
    for col in ["last", "std_recent", "pct_from_med"]:
        assert col in metrics_df.columns

    # "last" should be numeric
    assert pd.api.types.is_numeric_dtype(metrics_df["last"])

    # 5) render HTML
    html = render_html_report(hist_df, metrics_df)
    assert "<html" in html.lower()
    assert "Alpha Factory Drift Dashboard" in html
    assert "Summary metrics" in html
    assert "Recent history" in html

    # 6) emulate cli_drift finalization:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "drift_metrics.csv").write_text(metrics_df.to_csv(index=False), encoding="utf-8")
    (outdir / "drift_report.html").write_text(html, encoding="utf-8")

    # Check files landed
    assert (outdir / "drift_metrics.csv").exists()
    assert (outdir / "drift_report.html").exists()

    # quick sanity on the CSV text
    text_csv = (outdir / "drift_metrics.csv").read_text(encoding="utf-8")
    assert "pct_from_med" in text_csv
    assert "TF" in text_csv or "MR" in text_csv