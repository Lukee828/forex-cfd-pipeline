param(
  [string]$OutDir = "reports",
  [int]$Top = 50
)
$ErrorActionPreference = "Stop"

# Demo: small synthetic run; wire to your real dataset later.
python - <<'PYEOF'
import numpy as np, pandas as pd, os
from sklearn.linear_model import LogisticRegression
from src.analytics.feature_importance import compute_permutation_importance, save_report

os.makedirs("reports", exist_ok=True)

rng = np.random.default_rng(1)
n = 400
x1 = rng.normal(size=n)
x2 = rng.normal(size=n)
x3 = x1 * 0.5 + rng.normal(scale=0.1, size=n)  # correlated with x1
y = (x1 + 0.2*rng.normal(size=n) > 0).astype(int)
X = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})

imp = compute_permutation_importance(X, pd.Series(y), LogisticRegression(max_iter=400), n_splits=5, scoring="roc_auc")
save_report(imp, "reports/feature_importance.csv", "reports/feature_importance.html", top=50)
print(imp.head())
PYEOF
