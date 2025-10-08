$ErrorActionPreference = "Stop"
Write-Host "Running pre-commit on all files..." -ForegroundColor Cyan
pre-commit run --all-files
Write-Host "Pre-commit OK ✅" -ForegroundColor Green
