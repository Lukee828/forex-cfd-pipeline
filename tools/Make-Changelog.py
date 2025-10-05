#!/usr/bin/env python
# tools/Make-Changelog.py
from __future__ import annotations
import argparse
import os
import glob
import pandas as pd


def _fmt_pct(x):
    return f"{x:.2f}%" if pd.notna(x) else "—"


def _fmt2(x):
    return f"{x:.2f}" if pd.notna(x) else "—"


def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            s = (
                df[c]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(
                    ",", "*", regex=False
                )  # we don’t want commas to trip CSV parsing in GH
            )
            df[c] = pd.to_numeric(s, errors="coerce")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--max-top", type=int, default=10)
    ap.add_argument("--grid", default=None, help="optional explicit latest grid path")
    args = ap.parse_args()

    runs = os.path.abspath(args.runs)
    latest_grid = args.grid
    if not latest_grid:
        globs = sorted(
            [p for p in glob.glob(os.path.join(runs, "ma_grid_*")) if os.path.isdir(p)],
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )
        latest_grid = globs[0] if globs else None

    # Summary CSVs created by Compare-Grids.ps1/.py
    combined_csv = os.path.join(runs, "all_grids_combined.csv")
    stab_csv = os.path.join(runs, "grid_stability_by_bps.csv")
    cons_csv = os.path.join(runs, "best_params_consensus.csv")

    parts = []
    parts.append("# Release notes\n")

    # Top consensus section
    if os.path.isfile(cons_csv):
        df = pd.read_csv(cons_csv)
        df = coerce_numeric(
            df, ["sharpe_mean", "sharpe_std", "sharpe_range", "calmar_mean"]
        )
        top = df.sort_values(
            ["robust_score", "sharpe_mean", "calmar_mean"], ascending=False
        ).head(args.max_top)
        parts.append("## Top consensus (robust across bps & grids)\n")
        parts.append("| fast | slow | robust | Sharpeμ | Sharpeσ | Calmarμ | obs |\n")
        parts.append("|-----:|-----:|------:|--------:|--------:|--------:|----:|\n")
        for _, r in top.iterrows():
            parts.append(
                f"| {int(r['fast'])} | {int(r['slow'])} | "
                f"{_fmt2(r['robust_score'])} | {_fmt2(r['sharpe_mean'])} | "
                f"{_fmt2(r['sharpe_std'])} | {_fmt2(r['calmar_mean'])} | {int(r['obs'])} |\n"
            )
        parts.append("\n")

    # Per-bps stability section
    if os.path.isfile(stab_csv):
        df = pd.read_csv(stab_csv)
        df = coerce_numeric(df, ["sharpe_mean", "sharpe_std", "sharpe_range"])
        top = df.sort_values(["robust_score", "sharpe_mean"], ascending=False).head(
            min(args.max_top, 10)
        )
        parts.append("## Per-bps stability (top by robust score)\n")
        parts.append("| fast | slow |  bps | robust | Sharpeμ | Sharpeσ | grids |\n")
        parts.append("|-----:|-----:|-----:|------:|--------:|--------:|------:|\n")
        for _, r in top.iterrows():
            bps = "NA" if str(r["bps"]) == "nan" else int(r["bps"])
            parts.append(
                f"| {int(r['fast'])} | {int(r['slow'])} | {bps} | "
                f"{_fmt2(r['robust_score'])} | {_fmt2(r['sharpe_mean'])} | "
                f"{_fmt2(r['sharpe_std'])} | {int(r['grids'])} |\n"
            )
        parts.append("\n")

    # Latest grid section
    if latest_grid:
        parts.append(f"## Latest grid: `{os.path.basename(latest_grid)}`\n")
        for name in ("heatmap_sharpe.csv", "heatmap_calmar.csv"):
            p = os.path.join(latest_grid, name)
            if os.path.isfile(p):
                parts.append(f"- Attached: `{name}`\n")
        for name in ("heatmap_sharpe.png", "heatmap_calmar.png"):
            p = os.path.join(latest_grid, name)
            if os.path.isfile(p):
                parts.append(f"![{name}]({name})\n")
        parts.append("\n")

    # Files included
    parts.append("## Included artifacts\n")
    listed = []
    if os.path.isfile(combined_csv):
        listed.append(os.path.relpath(combined_csv, runs))
    if os.path.isfile(stab_csv):
        listed.append(os.path.relpath(stab_csv, runs))
    if os.path.isfile(cons_csv):
        listed.append(os.path.relpath(cons_csv, runs))
    for name in (
        "heatmap_sharpe.csv",
        "heatmap_calmar.csv",
        "heatmap_sharpe.png",
        "heatmap_calmar.png",
    ):
        p = os.path.join(latest_grid or "", name)
        if os.path.isfile(p):
            listed.append(os.path.relpath(p, runs))
    if listed:
        parts.append("\n".join(f"- `{x}`" for x in listed))
        parts.append("\n")

    print("".join(parts))


if __name__ == "__main__":
    main()
