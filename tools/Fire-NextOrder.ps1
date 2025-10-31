# tools/Fire-NextOrder.ps1
# Role:
#   Ask Python (bridge_mt5.fire_next_order) to actually send the staged
#   artifacts/live/next_order.json to MT5.
#
# SAFETY RECAP INSIDE fire_next_order():
#   - checks ai_lab/live_switch.json => allow_live must be true
#   - refuses if ticket.accept == false
#   - refuses if ticket_nonce already used (replay guard)
#   - checks allowed_symbols / side / size / session_block / news_block
#   - checks spread before sending
#   - after fill: logs FILL, enforces latency/slippage/spread_post
#   - if breach: auto FLATTEN ALL and log BREACH with source_nonce
#
# REQUIREMENTS:
#   - MT5 open, logged in, AutoTrading enabled, hedge account.
#   - You understand this MAY open OR immediately close positions,
#     depending on quality breakers.
param()
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "[Fire-NextOrder] LIVE EXECUTION REQUEST" -ForegroundColor Cyan
Write-Host "Will ONLY fire if:" -ForegroundColor Yellow
Write-Host "  • allow_live=true in ai_lab/live_switch.json" -ForegroundColor Yellow
Write-Host "  • ticket.accept=true and nonce not used" -ForegroundColor Yellow
Write-Host "  • symbol/size/session/news pass guard config" -ForegroundColor Yellow
Write-Host "  • spread is inside limits" -ForegroundColor Yellow
Write-Host "" -ForegroundColor Yellow
Write-Host "If breakers trip after fill, ALL positions will be FLATTENED." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""

# --- resolve paths ---
$repoRoot  = (Get-Location).Path
$srcPath   = Join-Path $repoRoot "src"
$venvPy    = Join-Path $repoRoot ".venv311\Scripts\python.exe"
$tmpScript = Join-Path $repoRoot "tmp_fire_next_order_exec.py"
$journal   = Join-Path $repoRoot "artifacts\live\journal.ndjson"

if (-not (Test-Path (Join-Path $repoRoot "src\alpha_factory\bridge_mt5.py"))) {
    Write-Host "[Fire-NextOrder] ERROR: bridge_mt5.py not found. Run from repo root." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $venvPy)) {
    Write-Host "[Fire-NextOrder] ERROR: .venv311\\Scripts\\python.exe not found." -ForegroundColor Red
    Write-Host "Activate correct venv first." -ForegroundColor Red
    exit 1
}

# --- python payload ---
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

Set-Content -Path $tmpScript -Value $pyBody -Encoding UTF8 -NoNewline

$stdout   = ""
$stderr   = ""
$exitCode = -999
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName                 = $venvPy
    $psi.Arguments                = "`"$tmpScript`""
    $psi.WorkingDirectory         = $repoRoot
    $psi.RedirectStandardOutput   = $true
    $psi.RedirectStandardError    = $true
    $psi.UseShellExecute          = $false
    $psi.CreateNoWindow           = $true
    $psi.Environment["PYTHONPATH"]= $srcPath
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

Remove-Item $tmpScript -ErrorAction SilentlyContinue

if ($stdout) { Write-Host $stdout }
if ($exitCode -ne 0) {
    if ($stderr) { Write-Host $stderr -ForegroundColor Red }
    Write-Host "[Fire-NextOrder] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Fire-NextOrder] Done." -ForegroundColor Green
Write-Host ""

if (Test-Path $journal) {
    Write-Host "---- journal tail (FILL / BREACH etc) ----" -ForegroundColor DarkGray
    Get-Content $journal | Select-Object -Last 10
    Write-Host "--------------------------------------" -ForegroundColor DarkGray
}