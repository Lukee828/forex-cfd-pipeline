<#
.SYNOPSIS
  Collect fill data from EA and append it to journal/fills_YYYYMMDD.jsonl.

.DESCRIPTION
  Reads artifacts/live/last_fill.json (written by AF_BridgeEA.mq5 after it
  attempts an order), and appends that record to artifacts/journal/fills_*.jsonl
  via bridge_contract.record_fill().

  Safe to run repeatedly; if last_fill.json hasn't changed, you'll just
  re-log same info (that's acceptable for now).

  PS7 only.
#>

param(
    [string]$RepoRoot = "C:\Users\speed\Desktop\forex-standalone"
)

# 1. Resolve python from pinned venv
$python = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[LiveCollect] ERROR: Python venv not found at $python" -ForegroundColor Red
    exit 1
}

# 2. Read last_fill.json
$fillPath = Join-Path $RepoRoot "artifacts\live\last_fill.json"
if (-not (Test-Path $fillPath)) {
    Write-Host "[LiveCollect] No last_fill.json found, nothing to journal." -ForegroundColor Yellow
    exit 0
}

$fillRaw = Get-Content -Raw -Path $fillPath -Encoding UTF8

# 3. Build inline Python payload that calls record_fill()
$pyCode = @"
from pathlib import Path
import json
from alpha_factory.bridge_contract import record_fill

repo_root = Path(r"$RepoRoot")
fill_path = Path(r"$fillPath")

fill_data = json.loads(fill_path.read_text(encoding="utf-8"))
jpath = record_fill(repo_root, fill_data)

print(f"[LiveCollect] appended fill to {jpath}")
"@

# 4. Write temp py
$tempPy = Join-Path $RepoRoot "artifacts\live\_collect_fill_tmp.py"
$targetDir = Split-Path $tempPy -Parent
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPy, ($pyCode -replace "`r`n","`n"), $utf8NoBom)

# 5. Run python
Write-Host "[LiveCollect] Logging fill from $fillPath ..." -ForegroundColor Cyan
& $python $tempPy
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "[LiveCollect] FAILED (exit $exitCode)" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[LiveCollect] Done." -ForegroundColor Green