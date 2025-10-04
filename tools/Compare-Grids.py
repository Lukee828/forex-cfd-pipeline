#!/usr/bin/env python
# tools/Compare-Grids.py

import argparse
import glob
import os
import re

import numpy as np
import pandas as pd


def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = (
                df[c]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_one_summary(grid_dir: str, prefer_bps: bool = True) -> pd.DataFrame:
    # Prefer the cost-sweep outputs if present
    bps_files = sorted(glob.glob(os.path.join(grid_dir, "summary_bps*.csv")))
    if prefer_bps and bps_files:
        frames = []
        for p in bps_files:
            m = re.search(r"summary_bps(\d+)\.csv$", os.path.basename(p))
            if not m:
                continue
            bps = int(m.group(1))
            df = pd.read_csv(p)
            df["bps"] = bps
            frames.append(df)
        if frames:
            out = pd.concat(frames, ignore_index=True)
            out["source"] = "summary_bps"
            return out

    # Fallback: single summary.csv (may not encode bps)
    p = os.path.join(grid_dir, "summary.csv")
    if os.path.isfile(p):
        df = pd.read_csv(p)
        df["bps"] = np.nan
        df["source"] = "summary"
        return df

    return pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs", help="root runs directory")
    ap.add_argument(
        "--max-grids", type=int, default=12, help="scan most recent N grids"
    )
    ap.add_argument(
        "--plot", action="store_true", help="write heatmap PNGs for latest grid"
    )
    ap.add_argument(
        "--top", type=int, default=10, help="rows to show in quick console preview"
    )
    args = ap.parse_args()

    runs = os.path.abspath(args.runs)
    grid_dirs = sorted(
        [d for d in glob.glob(os.path.join(runs, "ma_grid_*")) if os.path.isdir(d)],
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )[: args.max_grids]

    rows = []
    for gd in grid_dirs:
        base = os.path.basename(gd)
        df = load_one_summary(gd)
        if df.empty:
            continue

        # carry grid id
        df["grid"] = base

        # numeric coercions
        df = coerce_numeric(
            df,
            [
                "Total",
                "CAGR",
                "Vol",
                "Sharpe",
                "Sortino",
                "Calmar",
                "MaxDD",
                "WinRate",
                "Median",
            ],
        )

        # Ensure ints
        if "Trades" in df:
            df["Trades"] = (
                pd.to_numeric(df["Trades"], errors="coerce").fillna(0).astype(int)
            )

        rows.append(df)

    if not rows:
        print("No grids found / no summaries present.")
        return

    all_df = pd.concat(rows, ignore_index=True)

    # Write combined
    combined_csv = os.path.join(runs, "all_grids_combined.csv")
    all_df.to_csv(combined_csv, index=False)
    print("Wrote:", combined_csv, f"(rows={len(all_df)})")

    # ---- Stability across grids: by (fast, slow, bps)
    grp = all_df.groupby(["fast", "slow", "bps"], dropna=False)
    stab = pd.DataFrame(
        {
            "grids": grp["grid"].nunique(),
            "sharpe_mean": grp["Sharpe"].mean(),
            "sharpe_std": grp["Sharpe"].std(ddof=0),
            "sharpe_min": grp["Sharpe"].min(),
            "sharpe_max": grp["Sharpe"].max(),
        }
    ).reset_index()
    stab["sharpe_range"] = stab["sharpe_max"] - stab["sharpe_min"]
    stab["robust_score"] = stab["sharpe_mean"] - stab["sharpe_std"].fillna(0.0)
    stab_csv = os.path.join(runs, "grid_stability_by_bps.csv")
    stab.to_csv(stab_csv, index=False)
    print("Wrote:", stab_csv)

    # ---- Consensus w.r.t. bps AND grids (aggregate over both axes)
    grp2 = all_df.groupby(["fast", "slow"])
    cons = pd.DataFrame(
        {
            "obs": grp2.size(),
            "sharpe_mean": grp2["Sharpe"].mean(),
            "sharpe_std": grp2["Sharpe"].std(ddof=0),
            "sharpe_min": grp2["Sharpe"].min(),
            "sharpe_max": grp2["Sharpe"].max(),
            "calmar_mean": grp2["Calmar"].mean(),
        }
    ).reset_index()
    cons["sharpe_range"] = cons["sharpe_max"] - cons["sharpe_min"]
    cons["robust_score"] = cons["sharpe_mean"] - cons["sharpe_std"].fillna(0.0)
    cons_csv = os.path.join(runs, "best_params_consensus.csv")
    cons.sort_values(
        ["robust_score", "sharpe_mean", "calmar_mean"], ascending=False
    ).to_csv(cons_csv, index=False)
    print("Wrote:", cons_csv)

    # ---- Latest grid: export heatmap CSVs (Sharpe & Calmar)
    latest = grid_dirs[0]
    latest_df = all_df[all_df["grid"] == os.path.basename(latest)]
    if not latest_df.empty:
        heat_sharpe = latest_df.pivot_table(
            index="fast", columns="slow", values="Sharpe", aggfunc="first"
        )
        heat_calmar = latest_df.pivot_table(
            index="fast", columns="slow", values="Calmar", aggfunc="first"
        )
        heat_sharpe.to_csv(os.path.join(latest, "heatmap_sharpe.csv"))
        heat_calmar.to_csv(os.path.join(latest, "heatmap_calmar.csv"))
        print("Wrote:", os.path.join(latest, "heatmap_sharpe.csv"))
        print("Wrote:", os.path.join(latest, "heatmap_calmar.csv"))

        if args.plot and (not heat_sharpe.empty) and (not heat_calmar.empty):
            try:
                import matplotlib

                matplotlib.use(
                    "Agg"
                )  # 👈 Add this line to force headless backend (no Tcl/Tk needed)
                import matplotlib.pyplot as plt

                for name, mat in [("Sharpe", heat_sharpe), ("Calmar", heat_calmar)]:
                    fig = plt.figure(figsize=(8, 5))
                    plt.imshow(mat.values, aspect="auto")
                    plt.xticks(range(len(mat.columns)), mat.columns, rotation=45)
                    plt.yticks(range(len(mat.index)), mat.index)
                    plt.colorbar()
                    plt.title(f"{name} heatmap — {os.path.basename(latest)}")
                    outp = os.path.join(latest, f"heatmap_{name.lower()}.png")
                    plt.tight_layout()
                    plt.savefig(outp, dpi=140)
                    plt.close(fig)
                print("Wrote:", os.path.join(latest, "heatmap_sharpe.png"))
                print("Wrote:", os.path.join(latest, "heatmap_calmar.png"))
            except Exception as ex:
                print("Plot skipped (matplotlib not available):", ex)
    # ---- Quick console preview
    top = (
        cons.sort_values(
            ["robust_score", "sharpe_mean", "calmar_mean"], ascending=False
        )
        .head(args.top if args.top else 10)
        .loc[
            :,
            [
                "fast",
                "slow",
                "sharpe_mean",
                "sharpe_std",
                "sharpe_range",
                "calmar_mean",
                "obs",
            ],
        ]
    )
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print("\nTop consensus (across bps & grids):")
        print(top.to_string(index=False))


if __name__ == "__main__":
    main()
