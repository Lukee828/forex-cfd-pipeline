param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone",
    [string]$Symbol   = "EURUSD",
    [string]$Side     = "BUY",
    [double]$Size     = 0.32,
    [double]$Price    = 1.08652,
    [string]$TicketId = "1234567",
    [string]$Note     = "fill from EA"
)

$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[Bridge-Fill] ERROR: venv python not found at $python" -ForegroundColor Red
    exit 1
}

$pyCode = @"
from alpha_factory.bridge_contract import record_fill_from_ea
from alpha_factory.live_reconcile import build_execution_report

repo_root = r"$RepoRoot"

record_fill_from_ea(
    repo_root=repo_root,
    symbol="$Symbol",
    side="$Side",
    size=$Size,
    price_exec=$Price,
    ticket_id="$TicketId",
    note="$Note",
)

rep = build_execution_report(repo_root)
print("[Bridge-Fill] summary:", rep["summary"])
"@

$tempPy = Join-Path $RepoRoot "artifacts\live\_bridge_fill_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, ($pyCode -replace "`r`n","`n"), $utf8NoBom)

Write-Host "[Bridge-Fill] running EA fill ingest + reconciliation..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[Bridge-Fill] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[Bridge-Fill] Done." -ForegroundColor Green