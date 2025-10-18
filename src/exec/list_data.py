from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data")
    args = ap.parse_args()
    root = Path(args.root)
    files = list(root.rglob("*.parquet"))
    if not files:
        print("No Parquet files found under", root)
        return
    rows = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            idx = df.index
            start = idx.min()
            end = idx.max()
            rows.append({"file": str(f), "rows": len(df), "start": str(start), "end": str(end)})
        except Exception:
            rows.append({"file": str(f), "rows": "ERR", "start": "-", "end": "-"})
    out = pd.DataFrame(rows).sort_values("file")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
