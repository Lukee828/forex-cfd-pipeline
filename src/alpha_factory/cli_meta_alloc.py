import json
import argparse
import time
import pathlib
from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["equal", "ewma", "bayes"], default="ewma")
    p.add_argument("--metrics", type=str, help="JSON path with {sleeve:{sharpe,dd}}")
    p.add_argument("--outdir", default="artifacts/allocations")
    p.add_argument("--config", type=str, help="JSON with AllocatorConfig fields")
    args = p.parse_args(argv)

    cfg = AllocatorConfig(mode=args.mode)
    if args.config:
        cfg.__dict__.update(json.loads(pathlib.Path(args.config).read_text(encoding="utf-8")))

    if args.metrics:
        metrics = json.loads(pathlib.Path(args.metrics).read_text(encoding="utf-8"))
    else:
        metrics = {
            "TF": {"sharpe": 1.2, "dd": 0.06},
            "MR": {"sharpe": 1.0, "dd": 0.05},
            "VOL": {"sharpe": 0.8, "dd": 0.04},
        }

    w = MetaAllocator(cfg).allocate(metrics)
    ts = time.strftime("%Y%m%d_%H%M%S")
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    csv = outdir / f"{ts}_alloc.csv"
    csv.write_text(
        "Sleeve,Weight\n" + "\n".join(f"{k},{v}" for k, v in w.items()), encoding="utf-8"
    )
    print(json.dumps({"weights": w, "csv": str(csv)}, indent=2))


if __name__ == "__main__":
    main()
