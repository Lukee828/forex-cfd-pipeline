param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python tools\Smoke-TimeStop.py
if ($LASTEXITCODE -ne 0) { throw "TimeStop smoke failed." }

Write-Host "TimeStop smoke OK" -ForegroundColor Green
