from __future__ import annotations
import io
import base64
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd


def _png_data_url(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    fig.clf()
    import matplotlib.pyplot as plt

    plt.close("all")
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{data}"


def render_dashboards(
    df: pd.DataFrame,
    out_html: str | Path,
    *,
    title: str = "Feature Dashboards",
    max_features: Optional[int] = None,
) -> Path:
    """
    Build a simple HTML dashboard:
      - Correlation heatmap for numeric columns
      - Redundancy table (pairs with |corr| >= 0.9)
    Returns the output path.
    """
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    # Work on numeric-only subset
    num = df.select_dtypes(include=[np.number]).copy()
    if max_features and num.shape[1] > max_features:
        num = num.iloc[:, :max_features]

    # Correlation
    if num.shape[1] >= 2:
        corr = num.corr(numeric_only=True).fillna(0.0)
        # Heatmap plot (matplotlib only; no seaborn dependency)
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        im = ax.imshow(corr.values, aspect="auto")
        ax.set_xticks(range(corr.shape[1]))
        ax.set_yticks(range(corr.shape[1]))
        ax.set_xticklabels(corr.columns, rotation=90)
        ax.set_yticklabels(corr.columns)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Correlation heatmap")
        heatmap_url = _png_data_url(fig)
    else:
        heatmap_url = ""

    # Redundancy pairs (|corr| >= 0.9)
    pairs = []
    if num.shape[1] >= 2:
        c = corr.abs()
        cols = c.columns.to_list()
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                v = float(c.iloc[i, j])
                if v >= 0.9:
                    pairs.append((cols[i], cols[j], v))
    red_df = pd.DataFrame(
        pairs, columns=["feature_a", "feature_b", "abs_corr"]
    ).sort_values("abs_corr", ascending=False)

    # Build HTML
    html_parts = []
    css = (
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px}"
        " h1,h2{margin:0 0 8px}"
        " .card{padding:16px;border:1px solid #ddd;border-radius:12px;margin:16px 0}"
        " img{max-width:100%}"
        " table{border-collapse:collapse}"
        " th,td{padding:6px 8px;border:1px solid #ddd}"
    )
    header = f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>{css}</style>
    </head>
    <body>"""
    html_parts.append(header)
    html_parts.append(f"<h1>{title}</h1>")
    html_parts.append("<div class='card'><h2>Correlation heatmap</h2>")
    if heatmap_url:
        html_parts.append(f"<img alt='Correlation heatmap' src='{heatmap_url}' />")
    else:
        html_parts.append("<em>Not enough numeric features to plot.</em>")
    html_parts.append("</div>")

    html_parts.append(
        "<div class='card'><h2>High-correlation pairs (|corr| ≥ 0.9)</h2>"
    )
    if not red_df.empty:
        html_parts.append(red_df.to_html(index=False))
    else:
        html_parts.append("<em>No redundant pairs found at threshold 0.9.</em>")
    html_parts.append("</div>")

    html_parts.append("</body></html>")
    out_html.write_text("".join(html_parts), encoding="utf-8")
    return out_html
