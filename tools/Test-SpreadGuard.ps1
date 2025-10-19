param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-SpreadGuard.py"
if ($LASTEXITCODE -ne 0) { throw "SpreadGuard smoke failed." }

Write-Host "SpreadGuard smoke OK" -ForegroundColor Green
