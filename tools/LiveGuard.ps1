# tools/LiveGuard.ps1
# Phase 15 Live Arm Safety version.
# Purpose:
# - Run ExecutionPlanner to produce a TradePlan
# - Enforce live kill switch / BREACH / spread / staleness
# - Append INTENT to journal.ndjson
# - Write next_order.json ticket for AF_BridgeEA.mq5
# - Echo summary for operator audit

param(
    [string]$RepoRoot = "$(Get-Location)"
)

Write-Host "[LiveGuard] Running ExecutionPlanner -> next_order.json + journal.ndjson ..." -ForegroundColor Cyan

# We'll generate and run a short Python snippet on the fly, same style as before.
$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"

$pyCode = @"
import json, time
from pathlib import Path
from alpha_factory.execution_planner import ExecutionPlanner
from alpha_factory.bridge_contract import (
    tradeplan_to_contract,
    write_next_order,
    append_intent,
    guard_pretrade_allowed,
)

repo_root = Path(r"$RepoRoot")

# TODO: pull real spread / tick age from MT5 later
spread_pips = 1.2
last_tick_age_sec = 0.5

# Pre-trade safety gate. Raises RuntimeError if blocked.
guard_pretrade_allowed(
    repo_root,
    spread_pips=spread_pips,
    last_tick_age_sec=last_tick_age_sec,
)

planner = ExecutionPlanner(repo_root=repo_root)

tp = planner.build_trade_plan(
    feature_row={"dummy": 1.0},   # TODO: real live features
    base_size=1.0,                # planner applies hazard/risk/cost etc
    risk_cap_mult=1.0,            # from Risk Governor when wired
    symbol="EURUSD",
)

tp_dict = tp.to_dict()
contract = tradeplan_to_contract(tp_dict)

# Log INTENT immediately
append_intent(repo_root, contract)

# Write ticket for the EA
ticket_path = write_next_order(repo_root, contract)

print(f"[LiveGuard] wrote ticket: {ticket_path}")
print(f"[LiveGuard] contract.accept={contract['accept']} size={contract['size']}")
print(f"[LiveGuard] nonce={contract.get('ticket_nonce','?')}")
"@

# Write the Python snippet to artifacts/live/_emit_ticket_tmp.py with UTF-8 LF
$liveDir = Join-Path $RepoRoot "artifacts\live"
if (-not (Test-Path $liveDir)) {
    New-Item -ItemType Directory -Path $liveDir | Out-Null
}
$tempPy = Join-Path $liveDir "_emit_ticket_tmp.py"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, ($pyCode -replace "`r`n","`n"), $utf8NoBom)

# Exec
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[LiveGuard] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

# Timestamp for operator visibility
$tsNow = Get-Date -Format "dd.MM.yyyy HH:mm:ss"
Write-Host "[LiveGuard] timestamp=$tsNow" -ForegroundColor DarkGray

Write-Host "[LiveGuard] Done." -ForegroundColor Green