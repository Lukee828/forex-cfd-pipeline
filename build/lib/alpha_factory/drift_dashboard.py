"""Minimal registry dashboard utilities (CI-safe).
Saves PNGs under artifacts/registry_dash/ and returns file paths.
"""

from __future__ import annotations
from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import pandas as pd


def plot_alpha_performance(
    df_rank: pd.DataFrame, title: str = "Top Alphas", outfile: str | None = None
) -> str:
    """
    df_rank must include columns: ['alpha_id', 'value'] at minimum.
    """
    outdir = Path("artifacts/registry_dash")
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = str(outfile or outdir / "top_alphas.png")
    plt.figure(figsize=(9, 5))
    plt.bar(df_rank["alpha_id"], df_rank["value"])  # default colors (policy)
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()
    return outfile
