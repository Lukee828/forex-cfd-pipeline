param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-VolState.py"
if ($LASTEXITCODE -ne 0) { throw "VolState smoke failed." }

Write-Host "VolState smoke OK" -ForegroundColor Green
