from __future__ import annotations
import os, datetime as dt
from pathlib import Path
from typing import List
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def _find_files(root: str, pat: str) -> List[Path]:
    return sorted(Path(root).glob(pat))

def _ensure_synth(root: str) -> List[Path]:
    Path(root).mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d")
    f1 = Path(root) / f"features-{ts}-a.csv"
    f2 = Path(root) / f"features-{ts}-b.csv"
    if not f1.exists() and not f2.exists():
        df1 = pd.DataFrame({"sharpe":[1.2,0.8,0.3], "dd":[0.10,0.05,0.20]})
        df2 = pd.DataFrame({"sharpe":[1.1,0.7,0.4], "dd":[0.11,0.06,0.18]})
        df1.to_csv(f1, index=False)
        df2.to_csv(f2, index=False)
    return [p for p in [f1, f2] if p.exists()]

def load_feature_history(root: str = "artifacts") -> pd.DataFrame:
    files = _find_files(root, "features-*.parquet") + _find_files(root, "features-*.csv")
    if not files:
        files = _ensure_synth(root)
    rows = []
    for p in files:
        if p.suffix.lower() == ".parquet":
            df = pd.read_parquet(p)
        else:
            df = pd.read_csv(p)
        df["ts"] = p.stem.split("-")[-1]
        rows.append(df)
    return pd.concat(rows, ignore_index=True)

def compute_drift(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("ts").mean(numeric_only=True).sort_index()
    diff = g.diff().abs()
    out = pd.DataFrame({
        "avg_abs_change": diff.mean(axis=0),
        "std_change": diff.std(axis=0),
    })
    return out.sort_values("avg_abs_change", ascending=False)

def render_dashboard(drift: pd.DataFrame, out_html="artifacts/drift_dashboard.html"):
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure()
    ax = fig.gca()
    xs = np.arange(len(drift.index))
    ax.bar(xs, drift["avg_abs_change"].values)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(i) for i in drift.index], rotation=45, ha="right")
    ax.set_title("Feature Drift (avg_abs_change)")
    ax.set_ylabel("avg_abs_change")
    png = Path(out_html).with_suffix(".png")
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    # no f-string to avoid braces—simple concatenation:
    html = "<html><body><h2>Feature Drift</h2><img src=\"" + png.name + "\"/></body></html>"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote", out_html, "and", str(png))

def main():
    df = load_feature_history()
    drift = compute_drift(df)
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    drift.to_csv("artifacts/drift_summary.csv")
    render_dashboard(drift, "artifacts/drift_dashboard.html")

if __name__ == "__main__":
    main()