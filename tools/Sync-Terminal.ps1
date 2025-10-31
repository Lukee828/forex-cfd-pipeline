# tools/Sync-Terminal.ps1
# PowerShell 7 only.
# Role:
#   Push planner output (next_order.json + live_guard_config.json)
#   from the research repo into a specific MT5 terminal sandbox.
#
# Typical usage (manual cycle for now):
#   pwsh tools/LiveGuard.ps1
#   pwsh tools/Sync-Terminal.ps1
#
# After this, AF_BridgeEA.mq5 running in that terminal will see
# the new order and act (or skip) based on safety gates.

param(
    # Your research repo root. This is where LiveGuard.ps1 wrote artifacts/live/*
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone",

    # That MT5 terminal's MQL5\Files directory (Terminal A)
    [string]$TerminalFilesDir = "C:\Users\speed\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Files",

    # Optional: dump the ticket we pushed
    [switch]$VerboseCopy
)

Write-Host "[Sync-Terminal] Start sync..." -ForegroundColor Cyan

# Source folder in repo
$srcLiveDir = Join-Path $RepoRoot "artifacts\live"

$srcTicket = Join-Path $srcLiveDir "next_order.json"
$srcCfg    = Join-Path $srcLiveDir "live_guard_config.json"

if (-not (Test-Path $srcTicket)) {
    Write-Host "[Sync-Terminal] ERROR: $srcTicket not found. Run LiveGuard.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $srcCfg)) {
    Write-Host "[Sync-Terminal] WARN: $srcCfg not found. EA may refuse due to missing cfg." -ForegroundColor Yellow
}

# Ensure Terminal\Files directory exists
if (-not (Test-Path $TerminalFilesDir)) {
    Write-Host "[Sync-Terminal] Creating terminal dir: $TerminalFilesDir" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Path $TerminalFilesDir -Force | Out-Null
}

# Targets inside MT5 sandbox
$dstTicket = Join-Path $TerminalFilesDir "next_order.json"
$dstCfg    = Join-Path $TerminalFilesDir "live_guard_config.json"

# Helper: write UTF-8 w/out BOM and normalize to LF
function Write-Utf8LF {
    param(
        [string]$Src,
        [string]$Dst
    )

    $raw = Get-Content -Path $Src -Raw -Encoding UTF8
    $lf  = $raw -replace "`r`n","`n"

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Dst, $lf, $utf8NoBom)
}

Write-Host "[Sync-Terminal] Pushing ticket -> $dstTicket" -ForegroundColor Gray
Write-Utf8LF -Src $srcTicket -Dst $dstTicket

if (Test-Path $srcCfg) {
    Write-Host "[Sync-Terminal] Pushing cfg    -> $dstCfg" -ForegroundColor Gray
    Write-Utf8LF -Src $srcCfg -Dst $dstCfg
}

if ($VerboseCopy) {
    Write-Host "[Sync-Terminal] Preview ticket:" -ForegroundColor DarkCyan
    Get-Content $dstTicket | Write-Host
}

Write-Host "[Sync-Terminal] Done. EA should now see:" -ForegroundColor Green
Write-Host "  ticket: $dstTicket"
Write-Host "  cfg:    $dstCfg"