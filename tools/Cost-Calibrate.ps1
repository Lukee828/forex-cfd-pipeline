<#
.SYNOPSIS
  Phase 9 nightly / intraday job.
  Estimate execution cost conditions (liquidity band) and persist snapshot.

.DESCRIPTION
  - Builds a synthetic liquidity_band right now (placeholder).
  - Writes artifacts/cost/latest_cost.json via cost_model.write_cost_snapshot().
  - Mirrors Conformal-Calibrate.ps1 / Regime-Calibrate.ps1 style.

NOTE:
  Replace the synthetic section with:
    - recent avg spread in pips
    - fill slippage at your target size
    - time-of-day bucket (rollover, etc.)
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone",
    [string]$Symbol   = "EURUSD"
)

$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[Cost-Calibrate] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

$pyCode = @"
import pathlib, random
from alpha_factory.cost_model import write_cost_snapshot

repo_root = r"$RepoRoot"
symbol = "$Symbol"

# --- PLACEHOLDER HEURISTICS ---
# pretend we sampled spreads etc.
# a crude random bucket just to exercise the pipeline
band_choice = random.choices(
    population=["OK","THIN","DEAD"],
    weights=[0.7, 0.25, 0.05],
    k=1
)[0]

if band_choice == "DEAD":
    mult = 0.0
    note = "cost too high / liq dead"
elif band_choice == "THIN":
    mult = 0.6
    note = "reduced liquidity, widen spreads"
else:
    mult = 1.0
    note = "normal conditions"

out_dir = pathlib.Path(repo_root) / "artifacts" / "cost"
latest_path = write_cost_snapshot(
    out_dir=out_dir,
    symbol=symbol,
    liquidity_band=band_choice,
    cost_multiplier=mult,
    note=note,
)

print(f"[Cost-Calibrate] {symbol} band={band_choice} mult={mult}")
print(f"[Cost-Calibrate] wrote {latest_path}")
"@

$tempPy = Join-Path $RepoRoot "artifacts\cost\_cost_calibrate_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, $pyCode, $utf8NoBom)

Write-Host "[Cost-Calibrate] Running cost calibration with $python ..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[Cost-Calibrate] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Cost-Calibrate] Done." -ForegroundColor Green

# Optional cleanup:
# Remove-Item $tempPy -ErrorAction SilentlyContinue