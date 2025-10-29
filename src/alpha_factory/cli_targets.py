from __future__ import annotations

import argparse
import pathlib
import pandas as pd

from alpha_factory.alloc_io import load_latest_alloc
from alpha_factory.portfolio import to_targets


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--alloc-dir", default="artifacts/allocations")
    p.add_argument("--assets", nargs="+", required=True)
    p.add_argument("--cap", type=float, default=1.0)
    p.add_argument("--per-asset-cap", type=float, default=0.5, dest="per_asset_cap")
    p.add_argument("--out", default="artifacts/targets/latest.csv")
    args = p.parse_args(argv)

    # demo signals: zeros; replace with real sleeve signals in production
    idx = pd.date_range("2024-01-01", periods=1, freq="D")
    sleeves = {
        "TF": pd.Series([0.0], index=idx),
        "MR": pd.Series([0.0], index=idx),
        "VOL": pd.Series([0.0], index=idx),
    }

    alloc = load_latest_alloc(args.alloc_dir)
    t = to_targets(
        sleeves,
        alloc.weights,
        assets=args.assets,
        cap_exposure=args.cap,
        per_asset_cap=args.per_asset_cap,
    )

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(out, index=True)
    print("WROTE", out)


if __name__ == "__main__":
    main()
