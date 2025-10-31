# tools/Flatten-All.ps1
# Role: EMERGENCY FLATTEN.
#
# What happens:
#   - Imports emergency_flatten() from alpha_factory.bridge_mt5
#   - emergency_flatten():
#       * walks ALL open positions (hedge-compatible)
#       * closes them (direct close / close_by pairing)
#       * logs BREACH row to artifacts/live/journal.ndjson
#   - Script prints what got closed and warns if anything is still open.
#
# EXPECTATION:
#   - This WILL send market close orders and try to take you to FLAT NOW.
#
# SAFETY:
#   If you don't want to nuke all live exposure, Ctrl+C now.

param()

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "[Flatten-All] EMERGENCY FLAT" -ForegroundColor Yellow
Write-Host "This WILL close ALL OPEN POSITIONS in MT5 immediately." -ForegroundColor Yellow
Write-Host "Ctrl+C if you did not mean to nuke exposure." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""

# --- resolve paths ---
$repoRoot  = (Get-Location).Path
$srcPath   = Join-Path $repoRoot "src"
$venvPy    = Join-Path $repoRoot ".venv311\Scripts\python.exe"
$tmpScript = Join-Path $repoRoot "tmp_emergency_flatten_exec.py"
$journal   = Join-Path $repoRoot "artifacts\live\journal.ndjson"

# sanity: repo root
if (-not (Test-Path (Join-Path $repoRoot "src\alpha_factory\bridge_mt5.py"))) {
    Write-Host "[Flatten-All] ERROR: bridge_mt5.py not found. Run from repo root." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $venvPy)) {
    Write-Host "[Flatten-All] ERROR: .venv311\\Scripts\\python.exe not found." -ForegroundColor Red
    Write-Host "Activate correct venv first." -ForegroundColor Red
    exit 1
}

# --- python payload (runs emergency_flatten()) ---
$pyBody = @"
import sys, os
repo_root = r"$repoRoot"
repo_src  = r"$srcPath"

if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from alpha_factory.bridge_mt5 import emergency_flatten

if __name__ == "__main__":
    emergency_flatten()
"@

# --- write temp script ---
Set-Content -Path $tmpScript -Value $pyBody -Encoding UTF8 -NoNewline

# --- run python via ProcessStartInfo ---
$stdout   = ""
$stderr   = ""
$exitCode = -999
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName                   = $venvPy
    $psi.Arguments                  = "`"$tmpScript`""
    $psi.WorkingDirectory           = $repoRoot
    $psi.RedirectStandardOutput     = $true
    $psi.RedirectStandardError      = $true
    $psi.UseShellExecute            = $false
    $psi.CreateNoWindow             = $true
    $psi.Environment["PYTHONPATH"]  = $srcPath

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null   = $proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    $exitCode = $proc.ExitCode
}
catch {
    Write-Host "[Flatten-All] EXCEPTION launching python: $($_.Exception.Message)" -ForegroundColor Red
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    exit 1
}

# cleanup temp script
Remove-Item $tmpScript -ErrorAction SilentlyContinue

# echo Python output
if ($stdout) { Write-Host $stdout }

if ($exitCode -ne 0) {
    if ($stderr) { Write-Host $stderr -ForegroundColor Red }
    Write-Host "[Flatten-All] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Flatten-All] COMPLETE. All positions attempted closed and BREACH logged." -ForegroundColor Green
Write-Host ""

# tail audit for operator sanity
if (Test-Path $journal) {
    Write-Host "---- journal tail (BREACH rows etc) ----" -ForegroundColor DarkGray
    Get-Content $journal | Select-Object -Last 10
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
}