param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$python = ".\.venv\Scripts\python.exe"

& $python "tools\Smoke-BreakEvenGate.py"
if ($LASTEXITCODE -ne 0) { throw "BreakEvenGate smoke failed." }

Write-Host "BreakEvenGate smoke OK" -ForegroundColor Green
