# tools/LiveGuard.ps1
# Role: pre-trade guard / ticket builder.
# - Builds a proposed order ("ticket") and logs INTENT into journal.ndjson
# - Writes artifacts/live/next_order.json for Fire-NextOrder.ps1 to actually send.
# SAFETY:
#   * global kill switch        (ai_lab/live_switch.json -> allow_live:false blocks)
#   * symbol/side whitelist     (ai_lab/live_guard_config.json)
#   * max lot size check        (ai_lab/live_guard_config.json)
#   * session/news embargo      (ai_lab/live_guard_config.json)
#   * accept=false + safety_blocks[] if anything fails
# NOTE:
#   This script NEVER sends orders. It just stages them.

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "[LiveGuard] PRE-TRADE CONTRACT BUILD + SAFETY GATES" -ForegroundColor Magenta
Write-Host "This only ARMS the next_order.json. It does NOT send to broker." -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""

# ---------- repo paths ----------
$repoRoot    = (Get-Location).Path
$liveDir     = Join-Path $repoRoot "artifacts\live"
$ticketPath  = Join-Path $liveDir  "next_order.json"
$journalPath = Join-Path $liveDir  "journal.ndjson"

$switchPath  = Join-Path $repoRoot "ai_lab\live_switch.json"
$guardCfgPath= Join-Path $repoRoot "ai_lab\live_guard_config.json"

if (-not (Test-Path $liveDir)) {
    New-Item -ItemType Directory -Path $liveDir | Out-Null
}

# ---------- load kill switch ----------
# default: BLOCK if file missing or malformed
$liveEnabled = $false
if (Test-Path $switchPath) {
    try {
        $switchJson = Get-Content $switchPath -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($switchJson.allow_live -eq $true) {
            $liveEnabled = $true
        }
    } catch {
        Write-Host "[LiveGuard] WARNING: could not parse live_switch.json, defaulting allow_live=false" -ForegroundColor Yellow
    }
} else {
    Write-Host "[LiveGuard] WARNING: no ai_lab/live_switch.json found, defaulting allow_live=false" -ForegroundColor Yellow
}

# ---------- load guard config ----------
# fallback defaults if file missing
$allowedSymbols = @{
    "EURUSD" = [ordered]@{
        sides     = @("BUY")
        max_lots  = 0.35
    }
}
$sessionBlock   = $false
$newsBlock      = $false

try {
    if (Test-Path $guardCfgPath) {
        $cfg = Get-Content $guardCfgPath -Raw -ErrorAction Stop | ConvertFrom-Json

        if ($cfg.allowed_symbols) {
            $allowedSymbols = @{}
            foreach ($k in $cfg.allowed_symbols.PSObject.Properties.Name) {
                $allowedSymbols[$k.ToUpper()] = @{
                    sides    = @($cfg.allowed_symbols.$k.sides)
                    max_lots = [double]$cfg.allowed_symbols.$k.max_lots
                }
            }
        }

        if ($cfg.session_block -eq $true) { $sessionBlock = $true }
        if ($cfg.news_block    -eq $true) { $newsBlock    = $true }
    } else {
        Write-Host "[LiveGuard] NOTE: ai_lab/live_guard_config.json missing, using built-in defaults" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[LiveGuard] WARNING: could not parse live_guard_config.json, using built-in defaults" -ForegroundColor Yellow
}

# ---------- candidate order (stub / planner output) ----------
# Later this block will come from planner output. For now it's static.
$symbol        = "EURUSD"
$side          = "BUY"
$lots          = 0.35
$slPips        = 15
$tpPips        = 30
$timeStopBars  = 90
$evEst         = 0.012
$reasonTags    = @("manual_stub","risk_ok")

# ---------- gate evaluation ----------
$blockReasons = @()

if (-not $liveEnabled) {
    $blockReasons += "live_switch_disabled"
}

if ($sessionBlock) {
    $blockReasons += "session_blocked"
}

if ($newsBlock) {
    $blockReasons += "news_blocked"
}

# symbol / side / lot size whitelist
$upperSym = $symbol.ToUpper()
if (-not $allowedSymbols.ContainsKey($upperSym)) {
    $blockReasons += "symbol_not_allowed"
} else {
    $symSpec = $allowedSymbols[$upperSym]

    if ($symSpec.sides -notcontains $side.ToUpper()) {
        $blockReasons += "side_not_allowed"
    }

    $maxLots = [double]$symSpec.max_lots
    if ([double]$lots -gt $maxLots) {
        $blockReasons += "size_too_large"
    }
}

$accept = ($blockReasons.Count -eq 0)

if (-not $accept) {
    Write-Host "[LiveGuard] BLOCKED. Ticket will be accept=false" -ForegroundColor Red
    Write-Host " Reasons:" -ForegroundColor Red
    $blockReasons | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor Red }
} else {
    Write-Host "[LiveGuard] PASSED safety gates. Ticket is live-capable." -ForegroundColor Green
}

# ---------- build ticket obj ----------
$nowIso = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.ffffffK")  # ISO w/ microsec

$ticketObj = [ordered]@{
    as_of          = $nowIso
    ticket_nonce   = $nowIso
    symbol         = $symbol
    side           = $side
    size           = $lots
    accept         = $accept
    sl_pips        = $slPips
    tp_pips        = $tpPips
    time_stop_bars = $timeStopBars
    expected_value = $evEst
    reasons        = $reasonTags
    safety_blocks  = $blockReasons
}

# write next_order.json
$ticketJson = ($ticketObj | ConvertTo-Json -Depth 6)
Set-Content -Path $ticketPath -Value $ticketJson -Encoding UTF8 -NoNewline

# append INTENT row to journal.ndjson
$intentRowObj = [ordered]@{
    ts       = $nowIso
    type     = "INTENT"
    contract = $ticketObj
}
$intentLine = ($intentRowObj | ConvertTo-Json -Depth 6 -Compress)
Add-Content -Path $journalPath -Value $intentLine -Encoding UTF8

Write-Host ""
Write-Host "[LG] wrote ticket: $ticketPath" -ForegroundColor Cyan
Write-Host "[LG] contract.accept=$($ticketObj.accept) size=$($ticketObj.size)" -ForegroundColor Cyan
Write-Host "[LG] nonce=$($ticketObj.ticket_nonce)" -ForegroundColor Cyan
Write-Host "[LG] timestamp=$([DateTime]::UtcNow.ToString('dd.MM.yyyy HH:mm:ss UTC'))" -ForegroundColor Cyan

if (-not $accept) {
    Write-Host ""
    Write-Host "!!! SAFETY BLOCK ACTIVE !!!" -ForegroundColor Red
    Write-Host "Fire-NextOrder.ps1 SHOULD REFUSE to send this ticket." -ForegroundColor Red
}

Write-Host ""
Write-Host "[LiveGuard] Done." -ForegroundColor Green