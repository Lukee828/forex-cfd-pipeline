from __future__ import annotations
import os, glob, datetime as dt
import pandas as pd
from typing import Optional
from .meta_allocator import MetaAllocator, MetaAllocatorConfig

def _latest_feature_file(artifacts_dir: str = "artifacts") -> Optional[str]:
    pats = [
        os.path.join(artifacts_dir, "features-*.parquet"),
        os.path.join(artifacts_dir, "features-*.csv"),
    ]
    cand = []
    for p in pats: cand.extend(glob.glob(p))
    if not cand: return None
    cand.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cand[0]

def _load_features(path: str) -> pd.DataFrame:
    _, ext = os.path.splitext(path.lower())
    if ext == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)

def export_weights(artifacts_dir: str = "artifacts") -> str:
    src = _latest_feature_file(artifacts_dir)
    if not src:
        raise FileNotFoundError(f"no feature file found in {artifacts_dir}/")
    df = _load_features(src)
    cols = [c for c in df.columns if c in {"sharpe","dd"}]
    if not cols:
        raise ValueError("no sharpe/dd columns present in features dataframe")
    rows = df[cols]
    rs = {c.replace("risk_scale_",""): float(df[c].iloc[0])
          for c in df.columns if c.startswith("risk_scale_")}
    alloc = MetaAllocator(MetaAllocatorConfig())
    w = alloc.compute_weights(rows, risk_scale=rs or None)
    os.makedirs(artifacts_dir, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d")
    out_parquet = os.path.join(artifacts_dir, f"weights-{ts}.parquet")
    try:
        import pyarrow as _pa  # noqa: F401
        w.to_frame("weight").to_parquet(out_parquet, index=True)
        print(f"wrote {out_parquet}")
        return out_parquet
    except Exception:
        out_csv = os.path.join(artifacts_dir, f"weights-{ts}.csv")
        w.to_frame("weight").to_csv(out_csv, index=True)
        print(f"pyarrow missing; wrote {out_csv}")
        return out_csv

def main() -> None:
    export_weights("artifacts")

if __name__ == "__main__":
    main()