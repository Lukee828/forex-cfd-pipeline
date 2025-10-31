<#
.SYNOPSIS
  LiveGuard pre-trade gate (Phase 13).

.DESCRIPTION
  - Builds TradePlan via ExecutionPlanner.
  - Converts to contract, then applies:
      * live_enabled gate
      * spread sanity
      * staleness gate
      * size sanity
      * duplicate suppression
  - Writes next_order.json
  - Appends INTENT event to journal.ndjson
  - Emits summary.

  Still DRY-RUN SAFE: does not talk to MT5.

  After Phase 14, EA will:
    - read next_order.json
    - if accept==true and live_enabled==true, send order
    - call append_trade_fill() with execution info
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone"
)

$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[LiveGuard] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

$pyCode = @"
import json
from pathlib import Path
from datetime import datetime, timezone

from alpha_factory.execution_planner import ExecutionPlanner
from alpha_factory.bridge_contract import (
    build_live_safe_contract,
    write_next_order,
    append_trade_intent,
)

repo_root = Path(r"$RepoRoot").resolve()
live_dir = repo_root / "artifacts" / "live"
live_dir.mkdir(parents=True, exist_ok=True)

planner = ExecutionPlanner(repo_root=repo_root)

# TODO Phase 14: feed real quote spread + real model_age_sec
market_spread_pips = 1.2
model_age_sec = 1.0

tp = planner.build_trade_plan(
    feature_row={"dummy": 1.0},
    base_size=1.0,
    risk_cap_mult=1.0,
    symbol="EURUSD",
)

tp_dict = tp.to_dict()

# Phase 13 safety filter + duplicate throttle
contract = build_live_safe_contract(
    repo_root=repo_root,
    tp_dict=tp_dict,
    market_spread_pips=market_spread_pips,
    model_age_sec=model_age_sec,
)

ticket_path = write_next_order(repo_root, contract)

journal_path = live_dir / "journal.ndjson"
append_trade_intent(journal_path, contract)

summary = {
    "ticket_path": str(ticket_path),
    "accept": contract.get("accept", False),
    "size": contract.get("size", 0.0),
    "reasons": contract.get("reasons", []),
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

print(json.dumps(summary))
"@

$tempDir = Join-Path $RepoRoot "artifacts\live"
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}
$tempPy = Join-Path $tempDir "_liveguard_tmp.py"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $tempPy,
    ($pyCode -replace "`r`n","`n"),
    $utf8NoBom
)

Write-Host "[LiveGuard] Running ExecutionPlanner -> safety -> next_order.json + journal.ndjson ..." -ForegroundColor Cyan
$raw = & $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[LiveGuard] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

try {
    $parsed = $raw | ConvertFrom-Json
} catch {
    Write-Host "[LiveGuard] WARN: could not parse summary JSON" -ForegroundColor Yellow
    $parsed = $null
}

if ($parsed -ne $null) {
    Write-Host "[LiveGuard] wrote ticket: $($parsed.ticket_path)" -ForegroundColor Green
    Write-Host ("[LiveGuard] accept={0} size={1}" -f $parsed.accept,$parsed.size) -ForegroundColor Green
    Write-Host ("[LiveGuard] reasons={0}" -f ($parsed.reasons -join ";")) -ForegroundColor DarkGray
    Write-Host ("[LiveGuard] timestamp={0}" -f $parsed.timestamp) -ForegroundColor DarkGray
} else {
    Write-Host $raw
}

Write-Host "[LiveGuard] journal appended -> artifacts/live/journal.ndjson" -ForegroundColor Green
Write-Host "[LiveGuard] Done." -ForegroundColor Green