import pandas as pd
from pathlib import Path
from src.analytics.dashboards import render_dashboards


def test_render_dashboards(tmp_path: Path):
    df = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],  # perfectly correlated with x
            "z": [1, 0, 1, 0, 1],
            "cat": ["a", "a", "b", "b", "a"],
        }
    )
    out = tmp_path / "reports" / "dash.html"
    p = render_dashboards(df, out)
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    assert "<html>" in txt.lower()
