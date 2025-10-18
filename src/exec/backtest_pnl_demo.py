"""
Event-driven backtest demo.

Usage:
  python -m src.exec.backtest_pnl_demo --folder data/prices_1d --out_prefix DEMO
"""

from __future__ import annotations


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main() -> int:
    # Keep minimal; original demo logic removed for this locked-down build.
    print("backtest_pnl_demo: disabled in this build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
