# tools/Bridge-Fill.ps1
# Phase 15 Live Arm Safety version.
# Purpose:
# - Called (manually for now, later automated by EA hook)
# - Writes a FILL record into journal.ndjson
# - Runs enforce_postfill_limits() to possibly raise BREACH

param(
    [string]$RepoRoot = "$(Get-Location)",

    # These would normally come from AF_BridgeEA.mq5 at fill time:
    [string]$Symbol        = "EURUSD",
    [string]$Side          = "BUY",
    [double]$SizeExec      = 0.35,
    [double]$PriceExec     = 1.08652,
    [int]$TicketId         = 1234567,
    [string]$TicketNonce   = "demo-nonce-123",
    [double]$LatencySec    = 0.4,
    [double]$SlippagePips  = 0.2
)

Write-Host "[Bridge-Fill] Logging fill + enforcing postfill limits..." -ForegroundColor Cyan

$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"

$pyFill = @"
from pathlib import Path
from alpha_factory.bridge_contract import record_fill_from_ea, enforce_postfill_limits

repo_root = Path(r"$RepoRoot")

record_fill_from_ea(
    repo_root=repo_root,
    symbol=r"$Symbol",
    side=r"$Side",
    size_exec=$SizeExec,
    price_exec=$PriceExec,
    ticket_id=$TicketId,
    ticket_nonce=r"$TicketNonce",
    latency_sec=$LatencySec,
    slippage_pips=$SlippagePips,
)

enforce_postfill_limits(repo_root)

print("[Bridge-Fill] logged FILL + checked breach")
"@

# Write snippet to artifacts/live/_fill_tmp.py
$liveDir = Join-Path $RepoRoot "artifacts\live"
if (-not (Test-Path $liveDir)) {
    New-Item -ItemType Directory -Path $liveDir | Out-Null
}
$tempPy = Join-Path $liveDir "_fill_tmp.py"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, ($pyFill -replace "`r`n","`n"), $utf8NoBom)

& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[Bridge-Fill] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

$tsNow = Get-Date -Format "dd.MM.yyyy HH:mm:ss"
Write-Host "[Bridge-Fill] timestamp=$tsNow" -ForegroundColor DarkGray

Write-Host "[Bridge-Fill] Done." -ForegroundColor Green