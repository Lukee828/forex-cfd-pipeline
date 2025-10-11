import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold, KFold
from sklearn.base import clone


def compute_permutation_importance(
    X: pd.DataFrame,
    y: pd.Series,
    model,
    *,
    n_splits: int = 5,
    classification: bool = True,
    scoring: str = None,
    n_repeats: int = 10,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Leakage-safe permutation importance via cross-validation.
    For each fold: fit on train, compute PI on *validation* only.
    Returns mean/std importances across folds and repeats.
    """
    X = X.copy()
    y = y.copy()
    cv = (StratifiedKFold if classification else KFold)(
        n_splits=n_splits, shuffle=True, random_state=random_state
    )

    per_fold = []
    for tr, va in cv.split(X, y):
        est = clone(model)
        est.fit(X.iloc[tr], y.iloc[tr])
        pi = permutation_importance(
            est,
            X.iloc[va],
            y.iloc[va],
            scoring=scoring,
            n_repeats=n_repeats,
            random_state=random_state,
        )
        df = pd.DataFrame(
            {
                "feature": X.columns,
                "importance_mean": pi.importances_mean,
                "importance_std": pi.importances_std,
            }
        )
        per_fold.append(df)

    out = (
        pd.concat(per_fold)
        .groupby("feature", as_index=False)
        .agg(
            importance_mean=("importance_mean", "mean"),
            importance_std=("importance_std", "mean"),
        )
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )
    return out


def save_report(df: pd.DataFrame, csv_path: str, html_path: str, top: int = 50) -> None:
    df = df.head(top)
    df.to_csv(csv_path, index=False)
    (
        df.style.bar(subset=["importance_mean"], align="zero")
        .hide(axis="index")
        .to_html(html_path)
    )
