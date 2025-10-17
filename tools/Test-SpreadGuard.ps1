$env:PYTHONPATH = "$PWD;$PWD/src"
$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-SpreadGuard.py"
if ($LASTEXITCODE -ne 0) { throw "SpreadGuard smoke failed." }

Write-Host "SpreadGuard smoke OK" -ForegroundColor Green
