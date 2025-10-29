from __future__ import annotations
from pathlib import Path
import pandas as pd

from alpha_factory.alloc_io import load_latest_alloc, Allocation
from alpha_factory.portfolio import to_targets


def _write_latest_alloc(tmp: Path, weights: dict[str, float]) -> Path:
    d = tmp / "allocations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "latest.csv").write_text(
        "Sleeve,Weight\n" + "\n".join(f"{k},{v}" for k, v in weights.items()),
        encoding="utf-8",
    )
    return d


def test_alloc_to_targets_end_to_end(tmp_path: Path) -> None:
    # 1) Fake latest.csv
    d = _write_latest_alloc(tmp_path, {"TF": 0.5, "MR": 0.3, "VOL": 0.2})

    # 2) Load weights via API
    alloc: Allocation = load_latest_alloc(d)

    # 3) Build sleeve signals (already in [-1,+1])
    idx = pd.date_range("2024-02-01", periods=4, freq="h")
    tf = pd.Series([+1, 0, -1, 0], index=idx)
    mr = pd.Series([0, +1, 0, -1], index=idx)
    vol = pd.Series([0, 0, +1, 0], index=idx)

    # 4) Combine into per-asset targets
    assets = ["EURUSD", "GBPUSD", "USDJPY"]
    targets = to_targets(
        {"TF": tf, "MR": mr, "VOL": vol},
        alloc_weights=alloc.weights,
        assets=assets,
        cap_exposure=0.9,
        per_asset_cap=0.5,
    )

    # basic sanity
    assert list(targets.columns) == assets
    assert len(targets) == 4
    # per-row gross <= 1.0 and per-asset cap respected
    for i in range(len(targets)):
        row = targets.iloc[i]
        assert row.abs().sum() <= 1.0 + 1e-12
        assert (row.abs() <= 0.5 + 1e-12).all()
