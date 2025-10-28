from __future__ import annotations
import argparse
import json
import time
import pathlib
from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def main(argv=None):
    p = argparse.ArgumentParser("Meta Allocator CLI")
    p.add_argument("--mode", choices=["ewma", "equal", "bayes"], default="ewma")
    p.add_argument(
        "--metrics",
        required=False,
        default="configs/meta_metrics.json",
        help="Path to JSON with per-sleeve metrics {name:{sharpe,dd,...}}",
    )
    p.add_argument("--outdir", required=False, default="artifacts/allocations")
    p.add_argument("--write-latest", action="store_true", help="Also write allocations/latest.csv")
    args = p.parse_args(argv)

    # Read metrics (fallback to simple default if missing)
    mpath = pathlib.Path(args.metrics)
    if not mpath.exists():
        metrics = {
            "TF": {"sharpe": 1.2, "dd": 0.06},
            "MR": {"sharpe": 1.0, "dd": 0.05},
            "VOL": {"sharpe": 0.8, "dd": 0.04},
        }
    else:
        metrics = json.loads(mpath.read_text(encoding="utf-8"))

    alloc = MetaAllocator(AllocatorConfig(mode=args.mode)).allocate(metrics)

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    csv_ts = outdir / f"{ts}_alloc.csv"
    csv_ts.write_text(
        "Sleeve,Weight\n" + "\n".join(f"{k},{v}" for k, v in alloc.items()), encoding="utf-8"
    )
    print("WROTE:", csv_ts)

    if args.write_latest:
        latest = outdir / "latest.csv"
        latest.write_text(csv_ts.read_text(encoding="utf-8"), encoding="utf-8")
        print("UPDATED:", latest)


if __name__ == "__main__":
    main()
