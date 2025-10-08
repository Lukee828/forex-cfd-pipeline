param(
  [string]$Python = ".\\.venv\\Scripts\\python.exe"
)
$ErrorActionPreference = "Stop"

# Ensure src importable
$repoRoot = (Get-Location).Path
$env:PYTHONPATH = "$repoRoot" + ($(if ($env:PYTHONPATH) { ";" + $env:PYTHONPATH } else { "" }))

# Run smoke
& $Python "tools\\Smoke-Overlay.py" | Write-Host

Write-Host "Overlay test OK ✅" -ForegroundColor Green
