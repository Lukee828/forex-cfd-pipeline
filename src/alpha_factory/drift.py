from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import pandas as pd

# ---- 1) snapshot logging -------------------------------------------------

def record_snapshot(
    history_path: Path,
    timestamp: datetime,
    sleeve_weights: dict[str, float],
    gross_exposure: float,
) -> None:
    """
    Append one row to drift_history.csv:
    ts, TF, MR, VOL, gross
    Creates file with header if missing.
    """
    row = {"ts": timestamp.isoformat(), "gross": float(gross_exposure)}
    row.update({k: float(v) for k, v in sleeve_weights.items()})
    df_new = pd.DataFrame([row])
    if history_path.exists():
        df_old = pd.read_csv(history_path)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    history_path.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(history_path, index=False)

# ---- 2) load + metrics ---------------------------------------------------

def load_history(history_path: Path) -> pd.DataFrame:
    if not history_path.exists():
        raise FileNotFoundError(f"No drift history at {history_path}")
    df = pd.read_csv(history_path)
    # parse ts
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.sort_values("ts")
    return df

@dataclass
class DriftMetrics:
    metrics_df: pd.DataFrame  # rows: sleeve + gross, cols: stats
    html: str                 # rendered report

def compute_drift_metrics(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    """
    For each numeric column (TF, MR, VOL, gross) compute:
    - last value
    - rolling std over last N
    - pct change vs median of last N
    """
    numeric_cols = [c for c in df.columns if c not in ("ts",)]
    tail = df.tail(lookback)
    out_rows = []
    for col in numeric_cols:
        series = tail[col].astype(float)
        last = series.iloc[-1]
        stdv = float(series.std(ddof=0)) if len(series) > 1 else 0.0
        med = float(series.median())
        pct_from_med = (last - med) / med * 100.0 if med != 0 else 0.0
        out_rows.append(
            {
                "name": col,
                "last": last,
                "std_recent": stdv,
                "pct_from_med": pct_from_med,
            }
        )
    return pd.DataFrame(out_rows)

def render_html_report(df_hist: pd.DataFrame, metrics_df: pd.DataFrame) -> str:
    """
    Very simple inline HTML so we can view artifact in browser.
    """
    # mini table for metrics
    metrics_table = metrics_df.to_html(index=False, float_format=lambda x: f"{x:.4f}")
    # last rows preview
    tail_html = df_hist.tail(10).to_html(index=False, float_format=lambda x: f"{x:.4f}")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>AlphaFactory Drift Report</title>
<style>
body {{ font-family: sans-serif; color:#111; background:#fafafa; padding:1rem 2rem; }}
h1,h2 {{ font-weight:600; }}
table {{ border-collapse: collapse; font-size:14px; margin-bottom:1.5rem; }}
th, td {{ border:1px solid #ccc; padding:4px 8px; text-align:right; }}
th {{ background:#eee; text-align:center; }}
td:first-child, th:first-child {{ text-align:left; }}
.codeblock {{ font-family: monospace; font-size:12px; color:#555; background:#fff; border:1px solid #ddd; padding:8px; }}
</style>
</head>
<body>
<h1>Alpha Factory Drift Dashboard</h1>
<p>Latest snapshot of sleeve weights and gross exposure.</p>

<h2>Summary metrics (recent window)</h2>
{metrics_table}

<h2>Recent history (tail)</h2>
{tail_html}

<p class="codeblock">
Legend:<br/>
- last: most recent value<br/>
- std_recent: stdev over last N snapshots<br/>
- pct_from_med: distance from rolling median (%)<br/>
</p>

</body>
</html>
"""
    return html