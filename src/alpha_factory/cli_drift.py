from __future__ import annotations
import argparse, pathlib, json
from datetime import datetime
import pandas as pd

from alpha_factory.alloc_io import load_latest_alloc, apply_meta_weights
from alpha_factory.portfolio import clip_exposure
from alpha_factory.drift import (
    record_snapshot,
    load_history,
    compute_drift_metrics,
    render_html_report,
)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--alloc-dir", default="artifacts/allocations")
    p.add_argument("--targets-path", default="artifacts/targets/latest.csv")
    p.add_argument("--history-path", default="artifacts/history/drift_history.csv")
    p.add_argument("--outdir", default="artifacts/drift")
    p.add_argument("--lookback", type=int, default=10)
    args = p.parse_args(argv)

    alloc = load_latest_alloc(args.alloc_dir)  # gives Allocation(weights=...)
    # reconstruct gross exposure from targets CSV (sum abs across assets at last row)
    targ_path = pathlib.Path(args.targets_path)
    targets_df = pd.read_csv(targ_path, index_col=0)
    last_row = targets_df.tail(1).abs().sum(axis=1).iloc[0]
    gross_expo = float(last_row)

    # snapshot weights (TF/MR/VOL/etc.) and gross exposure
    record_snapshot(
        history_path=pathlib.Path(args.history_path),
        timestamp=datetime.utcnow(),
        sleeve_weights=alloc.weights,
        gross_exposure=gross_expo,
    )

    # now load full history and compute drift
    hist_df = load_history(pathlib.Path(args.history_path))
    metrics_df = compute_drift_metrics(hist_df, lookback=args.lookback)
    html = render_html_report(hist_df, metrics_df)

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    metrics_csv = outdir / "drift_metrics.csv"
    report_html = outdir / "drift_report.html"

    metrics_df.to_csv(metrics_csv, index=False)
    report_html.write_text(html, encoding="utf-8")

    print("WROTE", metrics_csv)
    print("WROTE", report_html)

if __name__ == "__main__":
    main()