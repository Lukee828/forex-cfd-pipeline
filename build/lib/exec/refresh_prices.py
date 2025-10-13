# src/exec/refresh_prices.py
from __future__ import annotations
import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def detect_out_folder(tf: str, override: str | None) -> Path:
    if override:
        return Path(override)
    return DATA / ("prices_1d" if tf.lower() in ("1d", "d", "daily") else "prices_1h")


def read_symbols(contracts_csv: Path) -> list[str]:
    df = pd.read_csv(contracts_csv)
    if "symbol" not in df.columns:
        raise SystemExit(f"'symbol' column missing in {contracts_csv}")
    # keep unique, non-null, as strings
    return [str(s) for s in df["symbol"].dropna().unique().tolist()]


def last_ts_in_parquet(p: Path) -> pd.Timestamp | None:
    try:
        df = pd.read_parquet(p, columns=["Close"])  # faster read
        # get index if datetime index, otherwise try Date column
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
            ts = df.index[-1]
        elif "Date" in df.columns and len(df):
            ts = pd.to_datetime(df["Date"].iloc[-1])
        else:
            return None
        # normalize to date (no tz issues for daily)
        ts = pd.Timestamp(ts)
        if ts.tz is not None:
            ts = ts.tz_convert("UTC")
        return ts
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"WARN: could not read {p}: {e}")
        return None


def build_cmd(symbol: str, tf: str, start: str, end: str, out_file: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.data.dukascopy_downloader",
        "--symbol",
        symbol,
        "--tf",
        tf,
        "--start",
        start,
        "--end",
        end,
        "--out",
        str(out_file),
    ]


def worker(
    symbol: str,
    tf: str,
    start: str,
    end: str,
    out_folder: Path,
    resume: bool,
    force: bool,
    dry_run: bool,
) -> tuple[str, str]:
    out_file = out_folder / f"{symbol}.parquet"
    eff_start, eff_end = start, end

    if out_file.exists() and resume and not force:
        last_ts = last_ts_in_parquet(out_file)
        if last_ts is not None:
            # add one bar forward depending on tf
            if tf.lower() in ("1d", "d", "daily"):
                eff_start = (last_ts.normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                eff_start = (last_ts + pd.Timedelta(hours=1)).strftime("%Y-%m-%d")
        # if eff_start > end → nothing to do
        if pd.Timestamp(eff_start) > pd.Timestamp(eff_end):
            return (symbol, f"up-to-date (last={str(last_ts)[:10]})")

    cmd = build_cmd(symbol, tf, eff_start, eff_end, out_file)
    if dry_run:
        return (symbol, "DRY-RUN " + " ".join(cmd))

    out_folder.mkdir(parents=True, exist_ok=True)
    cp = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if cp.returncode != 0:
        return (
            symbol,
            f"ERROR code={cp.returncode}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}",
        )
    return (symbol, f"OK → {out_file.name} [{eff_start}→{eff_end}]")


def main():
    ap = argparse.ArgumentParser(
        description="Refresh Dukascopy price files for all symbols in contracts.csv"
    )
    ap.add_argument(
        "--contracts_csv",
        default="config/contracts.csv",
        help="Path to contracts spec with 'symbol' column",
    )
    ap.add_argument("--tf", default="1d", choices=["1d", "1h"], help="Timeframe to download")
    ap.add_argument(
        "--start",
        default="2015-01-01",
        help="Start date YYYY-MM-DD (ignored if --resume finds newer)",
    )
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today UTC)")
    ap.add_argument(
        "--out_folder",
        default=None,
        help="Override output folder (default: data/prices_1d or prices_1h)",
    )
    ap.add_argument("--resume", action="store_true", help="Resume from last bar if file exists")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Force full re-download even if file exists",
    )
    ap.add_argument("--dry_run", action="store_true", help="Print what would run without executing")
    ap.add_argument("--max_workers", type=int, default=min(8, os.cpu_count() or 4))
    args = ap.parse_args()

    contracts_csv = (
        (ROOT / args.contracts_csv)
        if not Path(args.contracts_csv).is_absolute()
        else Path(args.contracts_csv)
    )
    if not contracts_csv.exists():
        raise SystemExit(f"Missing {contracts_csv}")

    symbols = read_symbols(contracts_csv)
    if not symbols:
        raise SystemExit("No symbols found in contracts.csv")

    end = args.end or today_yyyymmdd()
    out_folder = detect_out_folder(args.tf, args.out_folder)
    print(
        f"Symbols: {len(symbols)} | TF: {args.tf} | Out: {out_folder} | Start: {args.start} | End: {end}"
    )
    print(
        f"Options: resume={args.resume} force={args.force} dry_run={args.dry_run} workers={args.max_workers}"
    )

    futures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        for sym in symbols:
            futures.append(
                ex.submit(
                    worker,
                    sym,
                    args.tf,
                    args.start,
                    end,
                    out_folder,
                    args.resume,
                    args.force,
                    args.dry_run,
                )
            )
        for fut in as_completed(futures):
            sym, msg = fut.result()
            print(f"[{sym}] {msg}")


if __name__ == "__main__":
    main()
