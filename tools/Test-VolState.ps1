$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-VolState.py"
if ($LASTEXITCODE -ne 0) { throw "VolState smoke failed." }

Write-Host "VolState smoke OK" -ForegroundColor Green
