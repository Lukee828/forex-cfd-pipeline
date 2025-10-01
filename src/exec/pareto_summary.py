import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def pareto_front(df, xcol="maxdd", ycol="sharpe"):
    # Minimize x (drawdown; more negative is worse) → use absolute magnitude
    dx = df[xcol].abs()
    dy = df[ycol]
    order = np.lexsort((-dy.values, dx.values))  # best: small |dd|, large Sharpe
    mask = np.zeros(len(df), dtype=bool)
    best_sharpe = -np.inf
    best_dd = np.inf
    for idx in order:
        d = dx.iloc[idx]
        s = dy.iloc[idx]
        if d <= best_dd and s >= best_sharpe:
            mask[idx] = True
            best_dd = d
            best_sharpe = s
    return df[mask].copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary_csv", required=True)
    ap.add_argument("--out_csv", default=None)
    args = ap.parse_args()
    df = pd.read_csv(args.summary_csv)
    pf = pareto_front(df, xcol="maxdd", ycol="sharpe")
    out = args.out_csv or (Path(args.summary_csv).with_name("summary_pareto.csv"))
    pf.to_csv(out, index=False)
    print("Saved Pareto front to", out)


if __name__ == "__main__":
    main()
