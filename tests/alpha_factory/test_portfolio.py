from __future__ import annotations
import pandas as pd

from alpha_factory.portfolio import to_targets


def test_portfolio_targets_basic() -> None:
    # sleeve signals (already in [-1,+1])
    idx = pd.date_range("2024-01-01", periods=3, freq="H")
    tf = pd.Series([1, 0, -1], index=idx)
    mr = pd.Series([0, 1, 0], index=idx)
    vol = pd.Series([0, 0, 1], index=idx)

    alloc = {"TF": 0.5, "MR": 0.3, "VOL": 0.2}
    assets = ["EURUSD", "GBPUSD"]

    # cap exposure to 0.8, per-asset cap 0.6 (won't bind for equal split of 0.8/2 = 0.4)
    targets = to_targets(
        {"TF": tf, "MR": mr, "VOL": vol},
        alloc_weights=alloc,
        assets=assets,
        cap_exposure=0.8,
        per_asset_cap=0.6,
    )

    assert list(targets.columns) == assets
    assert len(targets) == 3

    # first bar: combo = 0.5 (TF=+1 @ 0.5), split equally -> 0.25 each
    assert abs(targets.iloc[0, 0] - 0.25) < 1e-9
    assert abs(targets.iloc[0, 1] - 0.25) < 1e-9

    # gross per row <= 1.0 and per-asset cap respected
    for i in range(len(targets)):
        row = targets.iloc[i]
        assert row.abs().sum() <= 1.0 + 1e-12
        assert (row.abs() <= 0.6 + 1e-12).all()
