#!/usr/bin/env python
import sys
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ_FILES = [
    ".pre-commit-config.yaml",
    ".gitignore",
    ".gitattributes",
    "src/exec/backtest_pnl_demo.py",
    "src/exec/make_orders.py",
    "src/exec/publish_mt5.py",
    "config/production.yaml",
    "config/contracts.csv",
]
REQ_DIRS = ["data/prices_1d", "src"]


def ok(m):
    print(f"✔ {m}")


def warn(m):
    print(f"⚠ {m}")


def err(m):
    print(f"✖ {m}")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def check_tree():
    missing = False
    for p in REQ_FILES:
        if (ROOT / p).exists():
            ok(f"{p} present")
        else:
            err(f"{p} MISSING")
            missing = True
    for d in REQ_DIRS:
        if (ROOT / d).exists():
            ok(f"{d} present")
        else:
            err(f"{d} MISSING")
            missing = True
    return not missing


def check_precommit():
    pc = ROOT / ".pre-commit-config.yaml"
    if not pc.exists():
        warn("pre-commit config missing (optional)")
        return
    if shutil.which("pre-commit") is None:
        warn("pre-commit not installed (pip install pre-commit)")
        return
    r = run("pre-commit run --show-diff-on-failure --all-files")
    if r.returncode == 0:
        ok("pre-commit hooks passed")
    else:
        warn("pre-commit modified files or found issues; re-run git add/commit")
        print(r.stdout or r.stderr)


def check_git_clean():
    r = run("git status --porcelain")
    if r.stdout.strip():
        warn("git status is not clean:")
        print(r.stdout)
    else:
        ok("git status clean")


def smoke_backtest():
    out_prefix = "DOCTOR_SMOKE"
    cmd = (
        "python -m src.exec.backtest_pnl_demo "
        "--folder data\\prices_1d "
        f"--out_prefix {out_prefix} "
        "--symbols EURUSD GBPUSD USDJPY"
    )
    print(f"RUN: {cmd}")
    r = run(cmd)
    if r.returncode != 0:
        err("smoke backtest failed")
        print(r.stdout or r.stderr)
        return False
    eq = ROOT / "data" / f"{out_prefix}_equity.csv"
    at = ROOT / "data" / f"{out_prefix}_attrib_sleeve.csv"
    if eq.exists() and at.exists():
        ok("smoke backtest outputs exist")
        return True
    warn("smoke backtest ran but outputs not found")
    return False


def main():
    print("== REPO DOCTOR ==")
    all_good = True
    if not check_tree():
        all_good = False
    check_precommit()
    check_git_clean()
    if not smoke_backtest():
        all_good = False
    print("\n==== SUMMARY ====")
    if all_good:
        print("Everything looks good ✅")
        sys.exit(0)
    else:
        print("Issues detected. Fix above and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
