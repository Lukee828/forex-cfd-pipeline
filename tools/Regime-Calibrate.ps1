<#
.SYNOPSIS
  Nightly job. Detect regime hazard (volatility / structural spike) and persist status.

.DESCRIPTION
  - Generates / loads recent realized volatility (placeholder synthetic for now).
  - Runs RegimeHazard threshold logic.
  - Saves artifacts/regime/latest_regime.json + archive file.
  - Mirrors Conformal-Calibrate.ps1 pattern.
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone",
    [int]$Window = 300
)

$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[Regime-Calibrate] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

$pyCode = @"
import numpy as np
from alpha_factory.regime_hazard import RegimeHazard
import pathlib

repo_root = r"$RepoRoot"
window = $Window

# TODO: replace this with real per-asset realized vol / ATR series
rng = np.random.default_rng(123)
base = rng.normal(loc=1.0, scale=0.05, size=window)
# simulate a shock on the last point to exercise hazard path
base[-1] = base.mean() + 0.4

haz = RegimeHazard(threshold=2.0)
state = haz.update_from_vol_series(base)

out_dir = pathlib.Path(repo_root) / "artifacts" / "regime"
latest_path = haz.save_status(out_dir)

print(f"[Regime-Calibrate] hazard={state.hazard} reason={state.reason} score={state.score:.3f}")
print(f"[Regime-Calibrate] wrote {latest_path}")
"@

$tempPy = Join-Path $RepoRoot "artifacts\regime\_regime_calibrate_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, $pyCode, $utf8NoBom)

Write-Host "[Regime-Calibrate] Running regime hazard calibration with $python ..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[Regime-Calibrate] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Regime-Calibrate] Done." -ForegroundColor Green

# Optional: keep temp for debugging or uncomment to cleanup:
# Remove-Item $tempPy -ErrorAction SilentlyContinue