<#
.SYNOPSIS
  Nightly job. Refit ConformalGate on recent trades and save bundle + summary.

.DESCRIPTION
  - Loads recent trades (placeholder loader for now).
  - Fits/updates ConformalGate.
  - Writes artifacts/conformal/*.json and latest_summary.json.
  - Designed for PS7 on Windows (no bash heredoc).
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone",
    [int]$Window = 2000
)

# 1. Resolve python from pinned venv
$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[Conformal-Calibrate] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

# 2. Build the Python payload dynamically.
# We inject RepoRoot/Window so nightly scheduler can call this non-interactively.
$pyCode = @"
import json, pathlib, datetime as dt
import numpy as np
from alpha_factory.conformal_gate import ConformalGate

def load_recent_trades(repo_root, window):
    # TODO: replace with real journal extraction.
    # Must return (features_matrix, labels_vector, feature_names_list)
    # Currently returns dummy synthetic data so pipeline + CI smoke without touching live fills.
    feat_names = ["vol_state_expansion","pivot_quality","spread_bps"]
    X = np.random.rand(window, len(feat_names))
    y = (X[:,0] + 0.2*X[:,1] - 0.1*X[:,2] > 0.5).astype(int)
    return X, y, feat_names

repo_root = r"$RepoRoot"
window = $Window

X, y, feat_names = load_recent_trades(repo_root, window)

gate = ConformalGate(
    coverage_target=0.9,
    calibration_window=window,
    min_samples=300,
    abstain_policy="skip",
)
gate.fit_from_history(X, y, feat_names)

out_dir = pathlib.Path(repo_root) / "artifacts" / "conformal"
out_path = gate.save_bundle(out_dir)

print(f"[Conformal-Calibrate] Wrote {out_path}")
"@

# 3. Write the payload to a temp file inside the repo so paths are predictable
$tempPy = Join-Path $RepoRoot "artifacts\conformal\_calibrate_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

# Ensure UTF-8 no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, $pyCode, $utf8NoBom)

# 4. Execute it with the venv python
Write-Host "[Conformal-Calibrate] Running calibration with $python ..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[Conformal-Calibrate] Calibration script failed (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Conformal-Calibrate] Done." -ForegroundColor Green

# 5. Optional cleanup
# Remove-Item $tempPy -ErrorAction SilentlyContinue