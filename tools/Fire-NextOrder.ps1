# tools/Fire-NextOrder.ps1
# Role: Send the staged order in artifacts/live/next_order.json to MT5.
#
# What happens:
#   - Imports fire_next_order() from alpha_factory.bridge_mt5
#   - fire_next_order():
#       * sanity checks (spread/staleness/etc.)
#       * sends market order with SL/TP
#       * logs FILL row into artifacts/live/journal.ndjson
#       * prints latency, slippage, ticket_id, etc.
#
# EXPECTATION:
#   - MetaTrader 5 is open, logged in, AutoTrading enabled.
#   - Account is HEDGING type.
#   - You understand this WILL OPEN A REAL POSITION.
#
# SAFETY:
#   This script DOES place a live order.
#   If you don't mean it, Ctrl+C NOW.

param()

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "[Fire-NextOrder] LIVE EXECUTION" -ForegroundColor Cyan
Write-Host "This WILL OPEN a real trade in MT5 with SL/TP." -ForegroundColor Yellow
Write-Host "Ctrl+C if you did not mean to do that." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""

# --- resolve paths ---
$repoRoot  = (Get-Location).Path
$srcPath   = Join-Path $repoRoot "src"
$venvPy    = Join-Path $repoRoot ".venv311\Scripts\python.exe"
$tmpScript = Join-Path $repoRoot "tmp_fire_next_order_exec.py"
$journal   = Join-Path $repoRoot "artifacts\live\journal.ndjson"

# sanity: repo root
if (-not (Test-Path (Join-Path $repoRoot "src\alpha_factory\bridge_mt5.py"))) {
    Write-Host "[Fire-NextOrder] ERROR: bridge_mt5.py not found. Run from repo root." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $venvPy)) {
    Write-Host "[Fire-NextOrder] ERROR: .venv311\\Scripts\\python.exe not found." -ForegroundColor Red
    Write-Host "Activate correct venv first." -ForegroundColor Red
    exit 1
}

# --- python payload (runs fire_next_order()) ---
$pyBody = @"
import sys, os
repo_root = r"$repoRoot"
repo_src  = r"$srcPath"

if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from alpha_factory.bridge_mt5 import fire_next_order

if __name__ == "__main__":
    fire_next_order()
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
    $psi.Environment["PYTHONPATH"]  = $srcPath  # belt+braces for import

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null   = $proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    $exitCode = $proc.ExitCode
}
catch {
    Write-Host "[Fire-NextOrder] EXCEPTION launching python: $($_.Exception.Message)" -ForegroundColor Red
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    exit 1
}

# cleanup temp script
Remove-Item $tmpScript -ErrorAction SilentlyContinue

# echo Python output
if ($stdout) { Write-Host $stdout }

if ($exitCode -ne 0) {
    if ($stderr) { Write-Host $stderr -ForegroundColor Red }
    Write-Host "[Fire-NextOrder] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Fire-NextOrder] Done." -ForegroundColor Green
Write-Host ""

# tail audit for operator sanity
if (Test-Path $journal) {
    Write-Host "---- journal tail (FILL rows etc) ----" -ForegroundColor DarkGray
    Get-Content $journal | Select-Object -Last 10
    Write-Host "--------------------------------------" -ForegroundColor DarkGray
}