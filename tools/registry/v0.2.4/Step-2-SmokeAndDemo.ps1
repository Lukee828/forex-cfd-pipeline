param(
  [string]$Python = ".\.venv311\Scripts\python.exe",
  [string]$PyTestArgs = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }

if (-not (Test-Path $Python)) { throw "Python not found at: $Python" }

# Ensure repo/src is on path for imports
$env:PYTHONPATH = (Resolve-Path .\src).Path
# Headless backend for matplotlib
$env:MPLBACKEND = "Agg"

Info "Running example_registry_usage.py"
& $Python "docs/example_registry_usage.py"
if ($LASTEXITCODE -ne 0) { throw "Example failed." }
Ok "Example ran."

Info "Running pytest smokes"
$pytest = @("-q")
if ($PyTestArgs) { $pytest = $PyTestArgs.Split(' ') }
& $Python -m pytest @pytest
if ($LASTEXITCODE -ne 0) { throw "Pytest failed." }
Ok "Pytest succeeded."
