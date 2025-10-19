param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
Write-Host "Running pre-commit on all files..." -ForegroundColor Cyan
pre-commit run --all-files
Write-Host "Pre-commit OK ✅" -ForegroundColor Green
