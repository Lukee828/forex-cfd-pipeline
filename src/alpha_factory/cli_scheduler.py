from __future__ import annotations
import argparse
import os
from alpha_factory.scheduler import make_default_scheduler


def main(argv=None) -> None:
    p = argparse.ArgumentParser("Research Scheduler")
    p.add_argument(
        "--run",
        nargs="+",
        default=["nightly"],
        help="Jobs to run (e.g. nightly, ensure_metrics, meta_alloc, emit_targets)",
    )
    p.add_argument("--assets", nargs="*", help="Override asset list (e.g. EURUSD GBPUSD)")
    p.add_argument("--cap", type=float, help="Exposure cap (default env AF_CAP or 1.0)")
    p.add_argument(
        "--per-asset-cap", type=float, help="Per-asset cap (default env AF_PER_ASSET_CAP or 0.5)"
    )
    p.add_argument(
        "--alloc-dir", help="Allocations dir (default env AF_ALLOC_OUT or artifacts/allocations)"
    )
    args = p.parse_args(argv)

    # Optional runtime overrides via env
    if args.assets:
        os.environ["AF_ASSETS"] = ",".join(args.assets)
    if args.cap is not None:
        os.environ["AF_CAP"] = str(args.cap)
    if args.per_asset_cap is not None:
        os.environ["AF_PER_ASSET_CAP"] = str(args.per_asset_cap)
    if args.alloc_dir:
        os.environ["AF_ALLOC_OUT"] = args.alloc_dir

    s = make_default_scheduler()
    s.run(args.run)


if __name__ == "__main__":
    main()
