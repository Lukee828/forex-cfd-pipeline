from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Optional, Sequence, Dict

import numpy as np
import pandas as pd


@dataclass
class CorrReport:
    features: Sequence[str]
    target: Optional[str]
    overall: pd.DataFrame
    by_regime: Dict[str, pd.DataFrame]
    leakage: Optional[pd.Series]
    meta: Dict[str, object]

    def to_csv(self) -> str:
        buf = io.StringIO()
        self.overall.to_csv(buf)
        return buf.getvalue()

    def to_html(self, title: str = "Feature Correlation Heatmap") -> str:
        # Simple, dependency-free heatmap using table + CSS
        df = self.overall.copy()
        # clip for color scaling
        vmin, vmax = -1.0, 1.0

        def cell(v: float) -> str:
            if pd.isna(v):
                return '<td class="nan">NA</td>'
            # map [-1,1] -> hue (red to blue) via green-less gradient
            # we’ll do a simple grayscale-to-blue; positive -> blue, negative -> red
            pct = (float(v) - vmin) / (vmax - vmin)
            # two-color: red->white->blue
            if v >= 0:
                r, g, b = int((1 - pct) * 255), int((1 - pct) * 255), 255
            else:
                r, g, b = 255, int((1 - pct) * 255), int((1 - pct) * 255)
            return f'<td style="background-color: rgb({r},{g},{b}); color:#000; text-align:right; padding:4px">{v:.3f}</td>'

        head = "".join(f"<th>{c}</th>" for c in df.columns)
        rows = []
        for idx, row in df.iterrows():
            cells = "".join(cell(x) for x in row.values)
            rows.append(f"<tr><th>{idx}</th>{cells}</tr>")
        body = "\n".join(rows)

        # Leakage block (if any)
        leak_html = ""
        if self.leakage is not None and not self.leakage.empty:
            leak_rows = "".join(
                f"<tr><td>{k}</td><td>{v:.6f}</td></tr>"
                for k, v in self.leakage.items()
            )
            leak_html = f"""
            <h2>Leakage Check vs. Target</h2>
            <table class="meta"><thead><tr><th>Feature</th><th>|corr(target)|</th></tr></thead>
            <tbody>{leak_rows}</tbody></table>
            """

        meta_html = f"<pre>{json.dumps(self.meta, indent=2)}</pre>"

        return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; }}
  h1, h2 {{ margin: 8px 0; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 4px 6px; }}
  th {{ background:#f7f7f7; text-align:left; position: sticky; top: 0; }}
  .nan {{ background:#f0f0f0; color:#666; text-align:center; }}
  .meta th, .meta td {{ text-align:left; }}
  .note {{ color:#666; }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <div class="note">Values are Pearson correlations in [-1, 1]. Darker blue = stronger positive; red = negative.</div>
  <h2>Overall</h2>
  <table>
    <thead><tr><th></th>{head}</tr></thead>
    <tbody>
      {body}
    </tbody>
  </table>
  {leak_html}
  <h2>Meta</h2>
  {meta_html}
</body>
</html>
"""


def _ensure_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    return df


def compute_correlations(
    df: pd.DataFrame,
    *,
    feature_cols: Optional[Sequence[str]] = None,
    target_col: Optional[str] = None,
    regime_col: Optional[str] = None,
    min_non_na: int = 3,
    leakage_abs_threshold: float = 0.95,
) -> CorrReport:
    """
    Compute overall feature correlation matrix, optional per-regime matrices, and simple leakage check.

    - df: dataframe with features (+ optional target + optional regime)
    - feature_cols: if None, uses all numeric columns except target/regime
    - target_col: optional; if provided, leakage check reports |corr(feature, target)|
    - regime_col: optional; if provided, returns by_regime correlations
    - min_non_na: minimum non-NA samples to compute correlations
    - leakage_abs_threshold: absolute corr threshold to flag as potential leakage

    Returns CorrReport with CSV/HTML helpers.
    """
    df = _ensure_df(df).copy()

    # choose features
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    drop_cols = set()
    if target_col and target_col in numeric_cols:
        drop_cols.add(target_col)
    if regime_col and regime_col in numeric_cols:
        # regime can be numeric or categorical; exclude from features regardless
        drop_cols.add(regime_col)
    features = feature_cols or [c for c in numeric_cols if c not in drop_cols]
    if not features:
        raise ValueError("No feature columns found/selected.")

    # overall corr
    overall = df[features].copy()
    overall = overall.dropna(how="all")
    # require enough samples
    if len(overall) < min_non_na:
        raise ValueError(
            f"Insufficient rows for correlation (min_non_na={min_non_na})."
        )
    overall_corr = overall.corr(method="pearson").fillna(0.0)

    # leakage check
    leakage = None
    if target_col and target_col in df.columns:
        tmp = df[[target_col] + features].dropna(how="any")
        if len(tmp) >= min_non_na:
            s = (
                tmp[features]
                .corrwith(tmp[target_col])
                .abs()
                .sort_values(ascending=False)
            )
            leakage = s[s >= leakage_abs_threshold]

    # per-regime corr
    by_regime: Dict[str, pd.DataFrame] = {}
    if regime_col and regime_col in df.columns:
        for key, g in df.groupby(regime_col):
            gg = g[features].dropna(how="all")
            if len(gg) >= min_non_na:
                by_regime[str(key)] = gg.corr(method="pearson").fillna(0.0)

    meta = dict(
        rows=int(len(df)),
        features=list(features),
        target=target_col,
        regime=regime_col,
        min_non_na=min_non_na,
        leakage_abs_threshold=float(leakage_abs_threshold),
        by_regime_keys=list(by_regime.keys()),
    )

    return CorrReport(
        features=features,
        target=target_col,
        overall=overall_corr,
        by_regime=by_regime,
        leakage=leakage,
        meta=meta,
    )
