from __future__ import annotations
from pathlib import Path
import pandas as pd
from alpha_factory.alloc_io import load_latest_alloc, validate_alloc, apply_meta_weights


def _write_alloc_csv(tmp: Path, rows: dict[str, float]) -> Path:
    d = tmp / "allocations"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "20240101_000000_alloc.csv"
    p.write_text(
        "Sleeve,Weight\n" + "\n".join(f"{k},{v}" for k, v in rows.items()), encoding="utf-8"
    )
    (d / "latest.csv").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    return d


def test_load_and_apply(tmp_path: Path) -> None:
    outdir = _write_alloc_csv(tmp_path, {"TF": 0.5, "MR": 0.3, "VOL": 0.2})
    alloc = load_latest_alloc(outdir)
    validate_alloc(alloc.weights)
    assert abs(sum(alloc.weights.values()) - 1.0) < 1e-6

    idx = pd.date_range("2024-01-01", periods=3, freq="H")
    tf = pd.Series([1, 0, -1], index=idx)
    mr = pd.Series([0, 1, 0], index=idx)
    vol = pd.Series([0, 0, 1], index=idx)
    combo = apply_meta_weights({"TF": tf, "MR": mr, "VOL": vol}, alloc.weights)
    assert list(combo.index) == list(idx)
    # quick sanity: first bar uses TF=+1 only @0.5
    assert abs(combo.iloc[0] - 0.5) < 1e-9
