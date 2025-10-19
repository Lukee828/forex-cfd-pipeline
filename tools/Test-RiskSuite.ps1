param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-SpreadGuard.ps1
if ($LASTEXITCODE -ne 0) { throw "SpreadGuard subtest failed." }

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-VolState.ps1
if ($LASTEXITCODE -ne 0) { throw "VolState subtest failed." }

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-BreakEvenGate.ps1
if ($LASTEXITCODE -ne 0) { throw "BreakEvenGate subtest failed." }

Write-Host "RiskSuite OK" -ForegroundColor Green

& .\.venv\Scripts\python.exe tools\Smoke-Signatures.py
if ($LASTEXITCODE -ne 0) { throw "Signature smoke failed." }

# Resilience smoke
pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-Resilience.ps1
if (0 -ne 0) { throw "Resilience subtest failed." }
