#requires -Version 7.0
param(
  [Parameter(Mandatory=$true)][string]$InputCsv,
  [string]$Target,
  [string]$Regime,
  [string[]]$Features,
  [double]$LeakageAbsThreshold = 0.95,
  [int]$MinNonNA = 3
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $PSCommandPath
$repo = git rev-parse --show-toplevel
Set-Location $repo

# Load CSV (expects header); rely on python/pandas for heavy lifting via pytest env or venv if present.
# We keep a pure-Python implementation and just call with python - <<EOF
$py = @"
import sys, json, pandas as pd
from pathlib import Path
from src.analytics.corr_matrix import compute_correlations

inp    = Path(r'$InputCsv')
target = r'$Target' if '$Target' else None
regime = r'$Regime' if '$Regime' else None
features = json.loads(r'''$([string]::Join(',', ($Features | ForEach-Object { '"' + ($_ -replace '"','\"') + '"' } )))''') if '$Features' else None
leak = float('$LeakageAbsThreshold')
minna = int('$MinNonNA')

df = pd.read_csv(inp)
rep = compute_correlations(df, feature_cols=features, target_col=target, regime_col=regime,
                           leakage_abs_threshold=leak, min_non_na=minna)

out_dir = Path('reports/correlation'); out_dir.mkdir(parents=True, exist_ok=True)
stamp = pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')
csv_path  = out_dir / f'feature_corr_{stamp}.csv'
html_path = out_dir / f'feature_corr_{stamp}.html'

csv_path.write_text(rep.to_csv(), encoding='utf-8')
html_path.write_text(rep.to_html(title='Feature Correlation Heatmap'), encoding='utf-8')

print(json.dumps({
  "csv": str(csv_path),
  "html": str(html_path),
  "features": list(rep.features),
  "target": rep.target,
  "by_regime": list(rep.by_regime.keys()),
  "leakage_count": 0 if rep.leakage is None else int(rep.leakage.shape[0])
}))
"@

# Pick python (prefer venv)
$pyExe = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }
$resp = & $pyExe - <<<$py
if ($LASTEXITCODE -ne 0) { throw "Python step failed." }

Write-Host $resp
