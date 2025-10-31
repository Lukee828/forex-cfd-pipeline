<#
.SYNOPSIS
  Phase 11 live safety gate / ticket emitter.

.DESCRIPTION
  - (Eventually) check risk guard conditions (daily DD, slippage, hazard cooldown, etc.).
  - If allowed:
      * Build ExecutionPlanner()
      * Generate TradePlan (sizing, TP/SL/time-stop, reasons)
      * Convert to broker contract
      * Write artifacts/live/next_order.json
      * Append journal line in artifacts/journal/*.jsonl

  This is the ONLY script that should feed AF_BridgeEA.mq5 in MT5.
  MT5 never talks directly to core strategy logic. It just reads next_order.json.

.NOTES
  PowerShell 7 on Windows. No interactive prompts.
  Safe to run from a scheduled job.
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone"
)

# 1. Resolve python from pinned venv
$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[LiveGuard] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

# 2. Risk gate logic (placeholder for now)
# Later: check drawdown, slippage, RegimeHazard cooldown, etc.
$allow = $true
if (-not $allow) {
    Write-Host "[LiveGuard] BLOCK: risk gate active, not emitting ticket." -ForegroundColor Yellow
    exit 0
}

# 3. Inline Python payload
# We explicitly set PYTHONPATH inside the Python code before imports so that
# alpha_factory.* resolves (same trick you use in pytest runs).
$pyCode = @"
import os
import sys
from pathlib import Path

repo_root = Path(r"$RepoRoot")

# Ensure src/ is on sys.path for imports
src_path = repo_root / "src"
os.environ["PYTHONPATH"] = str(src_path)
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from alpha_factory.execution_planner import ExecutionPlanner
from alpha_factory.bridge_contract import tradeplan_to_contract, write_next_order

# Build planner
planner = ExecutionPlanner(repo_root=repo_root)

# TODO Phase 12+: real feature_row, risk_cap_mult from Risk Governor,
# and direction/side from signal logic.
tp = planner.build_trade_plan(
    feature_row={"dummy": 1.0},
    base_size=1.0,
    risk_cap_mult=1.0,
    symbol="EURUSD",
)

tp_dict = tp.to_dict()

contract = tradeplan_to_contract(tp_dict)
ticket_path = write_next_order(repo_root, contract)

print(f"[LiveGuard] wrote ticket: {ticket_path}")
print(f"[LiveGuard] contract.accept={contract['accept']} size={contract['size']}")
"@

# 4. Write Python payload to temp file (UTF-8 no BOM, LF)
$tempPy = Join-Path $RepoRoot "artifacts\live\_emit_ticket_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $tempPy,
    ($pyCode -replace "`r`n","`n"),
    $utf8NoBom
)

# 5. Execute it with the venv python
Write-Host "[LiveGuard] Running ExecutionPlanner -> next_order.json ..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[LiveGuard] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[LiveGuard] Done." -ForegroundColor Green