from __future__ import annotations
import os
import sys
import runpy
from pathlib import Path


def _run_cli_scheduler(repo_root: Path, argv: list[str]) -> None:
    cli = repo_root / "src" / "alpha_factory" / "cli_scheduler.py"
    prev = sys.argv[:]
    sys.path.insert(0, str(repo_root / "src"))
    try:
        sys.argv = ["cli_scheduler.py", *argv]
        runpy.run_path(str(cli), run_name="__main__")
    finally:
        sys.argv = prev


def test_scheduler_nightly_writes_alloc_and_targets(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    # sandbox artifacts in tmp
    alloc_dir = tmp_path / "allocations"
    targets = tmp_path / "targets" / "latest.csv"
    os.environ["AF_ALLOC_OUT"] = str(alloc_dir)
    os.environ["AF_TARGETS_OUT"] = str(targets)
    os.environ["AF_ASSETS"] = "EURUSD,GBPUSD"

    _run_cli_scheduler(repo, ["--run", "nightly"])

    csvs = list(alloc_dir.glob("*_alloc.csv"))
    assert csvs, "no allocation CSV produced"
    assert targets.exists(), "targets/latest.csv missing"
    # simple shape check
    rows = targets.read_text(encoding="utf-8").strip().splitlines()
    assert rows and rows[0].startswith(","), "CSV header should start with comma then assets"
