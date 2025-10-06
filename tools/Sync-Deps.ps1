param(
  [string[]] $Files = @("requirements.txt", "dev-requirements.txt")
)
$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Missing .\.venv. Create it first." }

# Prefer module entrypoint (works even if pip-sync.exe not present)
$cmd = @($python, "-m", "piptools", "sync") + $Files
Write-Host ">>" ($cmd -join ' ')
& $python -m piptools sync @Files
if ($LASTEXITCODE -ne 0) { throw "pip-sync failed." }

Write-Host "Dependencies are in sync." -ForegroundColor Green
