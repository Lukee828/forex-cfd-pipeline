from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd


_EPS = 1e-12


def _ref_quantile_bins(ref: pd.Series, bins: int) -> np.ndarray:
    # Build quantile-based bin edges from reference
    qs = np.linspace(0.0, 1.0, bins + 1)
    edges = ref.dropna().quantile(qs).to_numpy(dtype=float)
    # Ensure edges are strictly increasing (dedupe)
    edges = np.unique(edges)
    if len(edges) < 2:
        # fallback to min/max +/- tiny eps
        v = ref.dropna().to_numpy()
        if v.size == 0:
            return np.array([0.0, 1.0])
        lo, hi = float(np.min(v)), float(np.max(v))
        if lo == hi:
            hi = lo + 1.0
        return np.array([lo, hi])
    return edges


def _hist_proportions(x: pd.Series, edges: np.ndarray) -> np.ndarray:
    vals = x.dropna().to_numpy(dtype=float)
    if vals.size == 0:
        h = np.zeros(len(edges) - 1, dtype=float)
    else:
        h, _ = np.histogram(vals, bins=edges)
    p = h.astype(float)
    s = p.sum()
    if s <= 0:
        p = np.full_like(p, 1.0 / len(p), dtype=float)
    else:
        p = p / s
    # smooth to avoid log(0)
    return np.clip(p, _EPS, 1.0)


def population_stability_index(ref: pd.Series, cur: pd.Series, *, bins: int = 10) -> float:
    """PSI between ref and current via reference quantile bins."""
    edges = _ref_quantile_bins(ref, bins)
    p_ref = _hist_proportions(ref, edges)
    p_cur = _hist_proportions(cur, edges)
    return float(np.sum((p_cur - p_ref) * np.log(p_cur / p_ref)))


@dataclass(frozen=True)
class DriftMetrics:
    column: str
    psi: float
    mean_ref: float
    mean_cur: float
    delta_mean: float
    std_ref: float
    std_cur: float
    std_ratio: float
    n_ref: int
    n_cur: int


def compute_tabular_drift(
    ref_df: pd.DataFrame,
    cur_df: pd.DataFrame,
    columns: Optional[Iterable[str]] = None,
    *,
    bins: int = 10,
) -> pd.DataFrame:
    """Compute PSI / mean / std drift per numeric column."""
    if columns is None:
        columns = [c for c in ref_df.columns if pd.api.types.is_numeric_dtype(ref_df[c])]
    rows = []
    for col in columns:
        if col not in cur_df.columns:
            continue
        ref = pd.to_numeric(ref_df[col], errors="coerce")
        cur = pd.to_numeric(cur_df[col], errors="coerce")
        psi = population_stability_index(ref, cur, bins=bins)
        mu_r, mu_c = float(ref.mean()), float(cur.mean())
        sd_r, sd_c = float(ref.std(ddof=1)), float(cur.std(ddof=1))
        if sd_r == 0.0:
            sd_r = _EPS
        std_ratio = float(sd_c / sd_r) if sd_r != 0 else np.nan
        rows.append(
            DriftMetrics(
                column=col,
                psi=psi,
                mean_ref=mu_r,
                mean_cur=mu_c,
                delta_mean=mu_c - mu_r,
                std_ref=sd_r,
                std_cur=sd_c,
                std_ratio=std_ratio,
                n_ref=int(ref.notna().sum()),
                n_cur=int(cur.notna().sum()),
            ).__dict__
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("psi", ascending=False).reset_index(drop=True)
    return out


def rolling_stats(series: pd.Series, window: int = 252) -> pd.DataFrame:
    """Rolling mean/std/vol (annualized) helper for drift monitoring of a single series."""
    s = pd.to_numeric(series, errors="coerce").astype(float)
    roll_mean = s.rolling(window, min_periods=max(2, window // 5)).mean()
    roll_std = s.rolling(window, min_periods=max(2, window // 5)).std()
    return pd.DataFrame({"roll_mean": roll_mean, "roll_std": roll_std})


def simple_html_report(
    metrics: pd.DataFrame,
    *,
    title: str = "Drift Report",
    path: Optional[str] = None,
) -> str:
    """Create a small, dependency-free HTML table report. Writes to `path` if provided."""
    css = """
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 16px; }
      h1 { font-size: 20px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { text-align: right; padding: 8px; border-bottom: 1px solid #ddd; }
      th:first-child, td:first-child { text-align: left; }
      tbody tr:hover { background: #fafafa; }
      .muted { color: #666; font-size: 12px; }
    </style>
    """
    if metrics is None or metrics.empty:
        body = "<p class='muted'>No metrics available.</p>"
    else:
        # Friendly rounding
        tbl = metrics.copy()
        num_cols = [c for c in tbl.columns if pd.api.types.is_numeric_dtype(tbl[c])]
        tbl[num_cols] = tbl[num_cols].astype(float).round(6)
        body = tbl.to_html(index=False, border=0)
    html = f"<!doctype html><html><head><meta charset='utf-8'>{css}<title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    if path:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    return html
