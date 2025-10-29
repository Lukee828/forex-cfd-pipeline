from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path


def test_cli_writes_alloc_csv(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "src" / "alpha_factory" / "cli_meta_alloc.py"

    outdir = tmp_path / "allocations"
    metrics = tmp_path / "m.json"
    metrics.write_text(
        json.dumps(
            {
                "TF": {"sharpe": 1.1, "dd": 0.06},
                "MR": {"sharpe": 1.0, "dd": 0.05},
                "VOL": {"sharpe": 0.8, "dd": 0.04},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # run the CLI via file path (matches nightly approach)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    res = subprocess.run(
        [
            sys.executable,
            str(cli),
            "--mode",
            "ewma",
            "--metrics",
            str(metrics),
            "--outdir",
            str(outdir),
            "--write-latest",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert res.returncode == 0, res.stderr

    # find the file and check weights
    csvs = sorted(outdir.glob("*_alloc.csv"))
    assert csvs, "No allocation CSV written"
    latest = outdir / "latest.csv"
    assert latest.exists(), "latest.csv not written"

    # sum to ~1.0
    rows = latest.read_text(encoding="utf-8").strip().splitlines()[1:]
    total = sum(float(r.split(",")[1]) for r in rows)
    assert abs(total - 1.0) < 1e-6, f"weights sum != 1.0 (got {total})"
