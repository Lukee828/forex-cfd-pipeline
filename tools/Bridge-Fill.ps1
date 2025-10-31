# tools/Bridge-Fill.ps1
# PowerShell 7 only. Non-interactive.
# Role:
#   - called by AF_BridgeEA.mq5 after MT5 executes an order
#   - append a FILL row to artifacts/live/journal.ndjson

param(
    [string]$RepoRoot,
    [string]$Symbol,
    [string]$Side,
    [double]$SizeExec,
    [double]$PriceExec,
    [string]$TicketId,
    [string]$TicketNonce,
    [double]$LatencySec,
    [double]$SlippagePips
)

# Build fill object in the same shape tests expect
$fill = [pscustomobject]@{
    type = "FILL"
    fill = @{
        as_of         = (Get-Date).ToUniversalTime().ToString("o")
        symbol        = $Symbol
        side          = $Side
        size_exec     = [double]$SizeExec
        price_exec    = [double]$PriceExec
        ticket_id     = $TicketId
        ticket_nonce  = $TicketNonce
        latency_sec   = [double]$LatencySec
        slippage_pips = [double]$SlippagePips
    }
}

# journal.ndjson path
$journalPath = Join-Path $RepoRoot "artifacts/live/journal.ndjson"
$journalDir  = Split-Path $journalPath -Parent

if (-not (Test-Path $journalDir)) {
    New-Item -ItemType Directory -Path $journalDir | Out-Null
}

# Append one NDJSON line
$line = ($fill | ConvertTo-Json -Depth 5 -Compress)
Add-Content -Path $journalPath -Encoding UTF8 -Value $line

Write-Host "[Bridge-Fill] wrote FILL nonce=$TicketNonce lots=$SizeExec price=$PriceExec slip=$SlippagePips lat=$LatencySec"