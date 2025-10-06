$ErrorActionPreference = "Stop"

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-SpreadGuard.ps1
if ($LASTEXITCODE -ne 0) { throw "SpreadGuard subtest failed." }

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-VolState.ps1
if ($LASTEXITCODE -ne 0) { throw "VolState subtest failed." }

pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-BreakEvenGate.ps1
if ($LASTEXITCODE -ne 0) { throw "BreakEvenGate subtest failed." }

Write-Host "RiskSuite OK" -ForegroundColor Green
