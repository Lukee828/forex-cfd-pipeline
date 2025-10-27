from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, Mapping, Tuple

from .meta_allocator import MetaAllocator, AllocatorConfig


def _load_json(p: str | Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _pairs_to_corr(pairs) -> Dict[Tuple[str, str], float]:
    out: Dict[Tuple[str, str], float] = {}
    for a, b, c in pairs:
        out[(str(a), str(b))] = float(c)
        out[(str(b), str(a))] = float(c)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser("meta-allocator")
    ap.add_argument("--metrics", default="tools/_demo_metrics.json")
    ap.add_argument("--prev", default="tools/_demo_prev.json")
    ap.add_argument("--corr", default="tools/_demo_corr.json")
    ap.add_argument("--config", default="configs/meta_allocator.json")
    ap.add_argument("--outcsv", default="")
    args = ap.parse_args(argv)

    cfg_dict = _load_json(args.config)
    cfg = AllocatorConfig(
        **{
            "mode": cfg_dict.get("mode", "ewma"),
            "min_weight": float(cfg_dict.get("min_weight", 0.0)),
            "max_weight": float(cfg_dict.get("max_weight", 1.0)),
            "turnover_penalty": float(cfg_dict.get("turnover_penalty", 0.02)),
            "corr_cap": float(cfg_dict.get("corr_cap", 0.75)),
            "corr_governor_strength": float(cfg_dict.get("corr_governor_strength", 0.5)),
            "ewma_alpha": float(cfg_dict.get("ewma_alpha", 0.3)),
        }
    )

    metrics: Mapping[str, Mapping[str, float]] = _load_json(args.metrics)
    prev: Mapping[str, float] = _load_json(args.prev)
    pairs = _load_json(args.corr)
    corr = _pairs_to_corr(pairs)

    alloc = MetaAllocator(cfg)
    w = alloc.allocate(metrics, prev_weights=prev, corr=corr)
    print(json.dumps(w))

    if args.outcsv:
        outp = Path(args.outcsv)
        outp.parent.mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(outp, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["timestamp", "sleeve", "weight"])
            for k, v in w.items():
                wr.writerow([now, k, float(v)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
