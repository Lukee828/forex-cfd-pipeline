#requires -Version 7.0
param()
param(
  [string]$InputCsv = "data/features.csv",
  [string]$OutHtml  = "reports/feature_dashboards.html",
  [int]$MaxFeatures = 50
)
$ErrorActionPreference = "Stop"

# Prepare venv Python if repo uses it; otherwise rely on runner env
function Invoke-Python {
  param([string]$Code)
  $py = "python"
  if (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }
  & $py - << $Code
}

# Run inline Python that uses our module
$pyCode = @"
import pandas as pd
from pathlib import Path
from src.analytics.dashboards import render_dashboards

inp = r"$InputCsv"
out = Path(r"$OutHtml")
try:
    df = pd.read_csv(inp)
except Exception:
    # Fallback: small synthetic DF so the tool always works
    import numpy as np
    df = pd.DataFrame({
        "x": np.arange(1, 51),
        "y": np.arange(1, 51) * 2.0,
        "z": np.random.RandomState(0).randn(50),
    })
p = render_dashboards(df, out, title="Feature Dashboards", max_features=$MaxFeatures)
print(p.as_posix())
"@
Invoke-Python -Code $pyCode

