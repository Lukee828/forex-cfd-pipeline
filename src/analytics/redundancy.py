import numpy as np
import pandas as pd


def redundancy_filter(
    X: pd.DataFrame,
    threshold: float = 0.95,
    rel_rmse_eps: float = 0.10,  # only drop if errors are tiny vs. signal scale
):
    """
    Drop near-duplicate features using a greedy pass:
      - Only consider *positive* Pearson correlations >= `threshold`
      - ALSO require small relative RMSE between the two series
    Keeps the first occurrence; drops later columns.

    Returns:
        kept (list[str]), dropped (list[str])
    """
    if X is None or len(X) == 0:
        return [], []

    X = X.select_dtypes(include=[np.number]).copy()
    cols = list(X.columns)
    if len(cols) <= 1:
        return cols, []

    corr = X.corr(method="pearson").fillna(0.0)

    # upper triangle (j>i) & positive only
    mask_upper = np.triu(np.ones_like(corr, dtype=bool), k=1)
    corr_pos_upper = corr.where(mask_upper & (corr > 0.0), other=0.0)

    def rel_rmse(a: pd.Series, b: pd.Series) -> float:
        s = pd.DataFrame({"a": a, "b": b}).dropna()
        if s.empty:
            return np.inf
        diff = s["a"].to_numpy(dtype=float) - s["b"].to_numpy(dtype=float)
        rmse = float(np.sqrt(np.mean(diff * diff)))
        sa = float(s["a"].std(ddof=0)) or 0.0
        sb = float(s["b"].std(ddof=0)) or 0.0
        denom = max(sa, sb, 1e-12)
        return rmse / denom

    to_drop = set()
    for col in cols:
        if col in to_drop:
            continue
        if col not in corr_pos_upper.index:
            continue

        row = corr_pos_upper.loc[col, :]
        cand = [c for c, r in row.items() if r >= threshold]

        near_dups = []
        for c2 in cand:
            if c2 in to_drop:
                continue
            if rel_rmse(X[col], X[c2]) <= rel_rmse_eps:
                near_dups.append(c2)

        to_drop.update(near_dups)

    kept = [c for c in cols if c not in to_drop]
    dropped = [c for c in cols if c in to_drop]
    return kept, dropped
