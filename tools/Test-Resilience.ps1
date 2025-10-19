param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
& $py tools\Smoke-Resilience.py
if ($LASTEXITCODE -ne 0) { throw "Resilience smoke failed." }
Write-Host "Resilience smoke OK" -ForegroundColor Green
