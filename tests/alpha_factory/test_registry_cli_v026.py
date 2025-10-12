import os
import subprocess
import sys
import pathlib


def _run(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pathlib.Path("src").resolve())
    res = subprocess.run(
        [sys.executable, "-m", "alpha_factory.registry_cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def test_cli_v026(tmp_path):
    db = tmp_path / "r.duckdb"
    # init + register a couple rows
    _run(["--db", str(db), "init"])
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
    )
    _run(
        [
            "--db",
            str(db),
            "register",
            "--cfg",
            "h2",
            "--metrics",
            "sharpe=2.2",
            "--tags",
            "demo",
        ]
    )
    # refresh + search
    _run(["--db", str(db), "refresh-runs"])
    out = _run(
        [
            "--db",
            str(db),
            "search",
            "--metric",
            "sharpe",
            "--min",
            "2.0",
            "--limit",
            "5",
        ]
    )
    assert "2.2" in out
    # export
    csvf = tmp_path / "best.csv"
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
            "2",
            "--format",
            "csv",
            "--out",
            str(csvf),
        ]
    )
    assert csvf.exists() and csvf.stat().st_size > 0
