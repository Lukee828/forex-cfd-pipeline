# tools/LiveGuard.ps1
# Role: Pre-trade guard / ticket builder.
# - Builds a proposed order ("ticket") and logs INTENT into journal.ndjson
# - Writes artifacts/live/next_order.json for Fire-NextOrder.ps1 to actually send.
# Current stub logic:
#   BUY EURUSD, 0.35 lots, fixed SL/TP, risk_ok.
#
# SAFETY:
# - This script does NOT send orders to MT5. It only stages intent + ticket.

param()

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "[LiveGuard] STUB CONTRACT GENERATOR (INTENT ONLY)" -ForegroundColor Magenta
Write-Host "This DOES NOT send to the broker." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""

# --- repo paths ---
$repoRoot   = (Get-Location).Path
$liveDir    = Join-Path $repoRoot "artifacts\live"
$ticketPath = Join-Path $liveDir  "next_order.json"
$journal    = Join-Path $liveDir  "journal.ndjson"

# sanity: are we in repo root (must contain src\alpha_factory)
if (-not (Test-Path (Join-Path $repoRoot "src\alpha_factory"))) {
    Write-Host "[LiveGuard] ERROR: run this from repo root (folder that has src\alpha_factory)." -ForegroundColor Red
    exit 1
}

# --- ensure dirs ---
if (-not (Test-Path $liveDir)) {
    New-Item -ItemType Directory -Path $liveDir | Out-Null
}

# --- build contract/ticket ---
$nowIso = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.ffffffK")  # high-res ISO UTC

$ticketObj = [ordered]@{
    as_of          = $nowIso
    ticket_nonce   = $nowIso
    symbol         = "EURUSD"
    side           = "BUY"
    size           = 0.35
    accept         = $true
    sl_pips        = 15
    tp_pips        = 30
    time_stop_bars = 90
    expected_value = 0.012
    reasons        = @("manual_stub","risk_ok")
}

# --- write next_order.json (human-readable-ish) ---
$ticketJson = ($ticketObj | ConvertTo-Json -Depth 5)
Set-Content -Path $ticketPath -Value $ticketJson -Encoding UTF8 -NoNewline

# --- append INTENT row to journal.ndjson (NDJSON style) ---
$intentRowObj = [ordered]@{
    ts       = $nowIso
    type     = "INTENT"
    contract = $ticketObj
}
$intentLine = ($intentRowObj | ConvertTo-Json -Depth 5 -Compress)
Add-Content -Path $journal -Value $intentLine -Encoding UTF8

Write-Host "[LG] wrote ticket: $ticketPath" -ForegroundColor Cyan
Write-Host "[LG] contract.accept=$($ticketObj.accept) size=$($ticketObj.size)" -ForegroundColor Cyan
Write-Host "[LG] nonce=$($ticketObj.ticket_nonce)" -ForegroundColor Cyan
Write-Host "[LG] timestamp=$([DateTime]::UtcNow.ToString('dd.MM.yyyy HH:mm:ss UTC'))" -ForegroundColor Cyan
Write-Host ""

Write-Host "[LiveGuard] Done." -ForegroundColor Green
Write-Host ""

# tail audit for operator sanity
if (Test-Path $journal) {
    Write-Host "---- journal tail (INTENT etc) ----" -ForegroundColor DarkGray
    Get-Content $journal | Select-Object -Last 10
    Write-Host "-----------------------------------" -ForegroundColor DarkGray
}