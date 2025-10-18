from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


def _no_subprocess(*args, **kwargs):
    raise RuntimeError("Blocked by local-only policy: subprocess is disabled")


# src/exec/reconcile.py

# import your chosen broker reader (e.g., mt5 or ib_insync) and reuse mapping from publisher


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders_csv", default="signals/orders.csv")
    ap.add_argument("--out_csv", default="reports/reconcile.csv")
    args = ap.parse_args()

    target = pd.read_csv(args.orders_csv).set_index("symbol")["target_position"]
    # TODO: read live positions into dict: live[symbol] = qty
    live = {}  # fill me
    df = pd.DataFrame({"target": target, "live": pd.Series(live)})
    df["diff"] = df["live"].fillna(0) - df["target"].fillna(0)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv)
    print("Saved", args.out_csv)


if __name__ == "__main__":
    main()
