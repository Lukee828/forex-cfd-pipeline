#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Daily orchestrator:

1) Run the demo backtest to (re)generate positions & analytics artifacts.
2) Build orders from those positions and latest prices.
3) Publish to MT5 (live by default).
4) Print a clean MTD summary (no tz warnings).

This script assumes the repo layout you've been using:

  data/prices_1d/
  data/costs_per_symbol.csv
  signals/positions.csv  (produced by backtest step)
  config/contracts.csv

Usage example:
  python -m src.exec.daily_run --out_prefix DAILY_LIVE --mt5_verify_positions
"""

from __future__ import annotations

import argparse
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]  # repo root


def run(cmd: list[str]) -> int:
    print("RUN:", " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def backtest_step(out_prefix: str, start: str | None = None, end: str | None = None) -> None:
    data_folder = str(ROOT / "data" / "prices_1d")
    costs_csv = str(ROOT / "data" / "costs_per_symbol.csv")

    args = [
        sys.executable, "-m", "src.exec.backtest_pnl_demo",
        "--folder", data_folder,
        "--costs_csv", costs_csv,
        "--out_prefix", out_prefix,
        "--target_ann_vol", "0.1",
        "--vol_lookback", "30",
        "--max_leverage", "2.0",
        "--w_tsmom", "1.0",
        "--w_xsec", "0.8",
        "--w_mr", "0.6",
        "--w_volcarry", "0.0",
        "--volcarry_top_q", "0.25",
        "--volcarry_bot_q", "0.25",
        "--volcarry_lookback", "42",
        "--mtd_soft", "-0.06",
        "--mtd_hard", "-0.1",
        "--gap_atr_k", "3.0",
        "--atr_lookback", "14",
        "--vol_spike_mult", "3.0",
        "--vol_spike_window", "60",
    ]
    if start:
        args += ["--start", start]
    if end:
        args += ["--end", end]

    rc = run(args)
    if rc != 0:
        print(f"Backtest step failed (rc={rc})", file=sys.stderr)
        # continue; downstream may still work with existing signals


def make_orders_step(nav: float, gross_cap: float, max_price_age_days: int) -> None:
    args = [
        sys.executable, "-m", "src.exec.make_orders",
        "--positions_csv", str(ROOT / "signals" / "positions.csv"),
        "--contracts_csv", str(ROOT / "config" / "contracts.csv"),
        "--prices_folder", str(ROOT / "data" / "prices_1d"),
        "--out_csv", str(ROOT / "signals" / "orders.csv"),
        "--nav", str(nav),
        "--gross_cap", str(gross_cap),
        "--max_price_age_days", str(max_price_age_days),
    ]
    run(args)


def publish_step(dry_run: bool, deviation: int) -> int:
    args = [
        sys.executable, "-m", "src.exec.publish_mt5",
        "--orders_csv", str(ROOT / "signals" / "orders.csv"),
        "--contracts_csv", str(ROOT / "config" / "contracts.csv"),
        "--dry_run", "true" if dry_run else "false",
        "--deviation", str(deviation),
    ]
    return run(args)


def summarize(out_prefix: str) -> None:
    try:
        eq_path = ROOT / "data" / f"{out_prefix}_equity.csv"
        if not eq_path.exists():
            print("[DAILY] Done.")
            return

        eq = pd.read_csv(eq_path, parse_dates=["ts"], infer_datetime_format=True)
        # make tz-aware (UTC) without throwing the warning
        eq["ts"] = pd.to_datetime(eq["ts"], utc=True, errors="coerce")
        eq = eq.dropna(subset=["ts"]).set_index("ts")
        if eq.empty:
            print("[DAILY] Done.")
            return

        # month-to-date stats using UTC index
        idx_utc = eq.index
        per = idx_utc.to_period("M")
        last_month = per[-1]
        eq_month = eq[per == last_month]
        if not eq_month.empty:
            start_eq = float(eq_month["portfolio_equity"].iloc[0])
            end_eq = float(eq_month["portfolio_equity"].iloc[-1])
            mtd = (end_eq / start_eq) - 1.0
            print(f"[DAILY] MTD: {mtd:.2%} | Last {len(eq_month)} obs.")
    except Exception as ex:
        print(f"WARN: summary failed: {ex}", file=sys.stderr)
    finally:
        print("[DAILY] Done.")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Daily run orchestrator")
    p.add_argument("--config", default=str(ROOT / "config" / "production.yaml"))
    p.add_argument("--out_prefix", default="DAILY_RUN")
    p.add_argument("--mt5_verify_positions", action="store_true", help="(reserved) include MT5 verification in publisher")
    p.add_argument("--nav", type=float, default=1_000_000.0)
    p.add_argument("--gross_cap", type=float, default=0.20)
    p.add_argument("--max_price_age_days", type=int, default=7)
    p.add_argument("--deviation", type=int, default=50)
    p.add_argument("--dry_run_publish", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # 1) Backtest / signals refresh
    backtest_step(out_prefix=args.out_prefix)

    # 2) Orders from positions
    make_orders_step(nav=args.nav, gross_cap=args.gross_cap, max_price_age_days=args.max_price_age_days)

    # 3) Publish (live by default)
    rc = publish_step(dry_run=args.dry_run_publish, deviation=args.deviation)
    if rc != 0:
        print("Publish step reported errors (see above).", file=sys.stderr)

    # 4) Summary
    summarize(args.out_prefix)


if __name__ == "__main__":
    main()
