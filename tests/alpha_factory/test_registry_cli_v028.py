import os
import pathlib
import subprocess
import sys


def _run(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pathlib.Path("src").resolve())
    return subprocess.run(
        [sys.executable, "-m", "alpha_factory.registry_cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_v028(tmp_path):
    db = tmp_path / "r.duckdb"
    best = tmp_path / "best.csv"
    summary = tmp_path / "summary.html"
    assert _run(["--db", str(db), "init"]).returncode == 0
    assert (
        _run(
            [
                "--db",
                str(db),
                "register",
                "--cfg",
                "h1",
                "--metrics",
                "sharpe=1.8",
                "--tags",
                "demo",
            ]
        ).returncode
        == 0
    )
    assert (
        _run(
            [
                "--db",
                str(db),
                "register",
                "--cfg",
                "h2",
                "--metrics",
                "sharpe=2.4",
                "--tags",
                "demo",
            ]
        ).returncode
        == 0
    )
    assert (
        _run(
            [
                "--db",
                str(db),
                "export",
                "--what",
                "best",
                "--metric",
                "sharpe",
                "--top",
                "1",
                "--format",
                "csv",
                "--out",
                str(best),
            ]
        ).returncode
        == 0
    )
    assert (
        _run(
            [
                "--db",
                str(db),
                "export",
                "--what",
                "summary",
                "--metric",
                "sharpe",
                "--format",
                "html",
                "--out",
                str(summary),
            ]
        ).returncode
        == 0
    )
    assert best.exists() and best.stat().st_size > 0
    assert summary.exists() and summary.stat().st_size > 0
