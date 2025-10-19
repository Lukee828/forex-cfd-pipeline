param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python tools\Smoke-TimeStop.py
if ($LASTEXITCODE -ne 0) { throw "TimeStop smoke failed." }

Write-Host "TimeStop smoke OK" -ForegroundColor Green
