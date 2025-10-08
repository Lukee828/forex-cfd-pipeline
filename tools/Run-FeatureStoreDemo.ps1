#requires -Version 7.0
param(
  [string]$DbPath = "runs/fs_demo/fs.db",
  [string]$Symbol = "EURUSD",
  [int]$Rows = 10
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Path $PSScriptRoot -Parent
$py   = Join-Path $root ".venv\Scripts\python.exe"
$src  = Join-Path $root "src"
$pth  = Join-Path $root ".venv\Lib\site-packages\repo_src.pth"
$demo = Join-Path $root "examples\use_feature_store.py"

Write-Host ">>> FeatureStore demo runner" -ForegroundColor Cyan

if (-not (Test-Path $py))  { throw "Python not found: $py" }
if (-not (Test-Path $demo)) { throw "Example not found: $demo" }

# Ensure site-packages points to ./src so 'feature' is importable.
if (-not (Test-Path $pth) -or (Get-Content -LiteralPath $pth -Raw) -ne $src) {
  New-Item -ItemType Directory -Force -Path (Split-Path $pth) | Out-Null
  $src | Set-Content -LiteralPath $pth -Encoding ASCII
  Write-Host "• Wrote $pth -> $src" -ForegroundColor DarkGray
}

# Ensure DB folder exists
$fullDb = Join-Path $root $DbPath
New-Item -ItemType Directory -Force -Path (Split-Path $fullDb) | Out-Null

Write-Host "• Running demo..." -ForegroundColor Yellow
& $py $demo --db $fullDb --symbol $Symbol --rows $Rows
if ($LASTEXITCODE) { throw "Demo failed with exit code $LASTEXITCODE" }

Write-Host "• Success." -ForegroundColor Green
Write-Host "  DB path: $fullDb" -ForegroundColor Gray
