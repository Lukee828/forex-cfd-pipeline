param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = (& git rev-parse --show-toplevel 2>$null) ?? (Get-Location).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "py" }

# ensure repo_root.pth (so 'import src' works)
$pth = Join-Path $root "tools/Create-RepoRootPth.ps1"
if (Test-Path $pth) { pwsh -NoProfile -ExecutionPolicy Bypass -File $pth | Out-Host }

$smoke = Join-Path $root "tools\Smoke-AlphaFactory.py"
& $python $smoke
if ($LASTEXITCODE -ne 0) { throw "AlphaFactory smoke failed." }
Write-Host "AlphaFactory smoke OK" -ForegroundColor Green
