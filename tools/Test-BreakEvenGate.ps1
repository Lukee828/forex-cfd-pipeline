param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-BreakEvenGate.py"
if ($LASTEXITCODE -ne 0) { throw "BreakEvenGate smoke failed." }

Write-Host "BreakEvenGate smoke OK" -ForegroundColor Green
