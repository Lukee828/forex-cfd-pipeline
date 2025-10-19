param()
<# Step-1-SmokeAndExport.ps1 (PS7) #>
param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
param(
  [string]$Python = ".\.venv311\Scripts\python.exe",
  [string]$Db     = "$PWD\tmp_v028.duckdb",
  [string]$Best   = "$PWD\best_v028.csv",
  [string]$Summary= "$PWD\summary_v028.html"
)
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Resolve-Path .\src).Path
$env:MPLBACKEND = "Agg"

Write-Host "[INFO] Init schema" -ForegroundColor Cyan
& $Python -m alpha_factory.registry_cli --db $Db init

Write-Host "[INFO] Register sample rows" -ForegroundColor Cyan
& $Python -m alpha_factory.registry_cli --db $Db register --cfg h1 --metrics "sharpe=1.8" --tags demo | Out-Null
& $Python -m alpha_factory.registry_cli --db $Db register --cfg h2 --metrics "sharpe=2.4" --tags demo | Out-Null

Write-Host "[INFO] Best (top 1)" -ForegroundColor Cyan
& $Python -m alpha_factory.registry_cli --db $Db export --what best --metric sharpe --top 1 --format csv --out $Best
if (-not (Test-Path $Best)) { throw "Best CSV not created: $Best" }

Write-Host "[INFO] Summary (html)" -ForegroundColor Cyan
& $Python -m alpha_factory.registry_cli --db $Db export --what summary --metric sharpe --format html --out $Summary
if (-not (Test-Path $Summary)) { throw "Summary HTML not created: $Summary" }

Write-Host "== BEST CSV (head) ==" -ForegroundColor Yellow
Get-Content $Best | Select-Object -First 5

Write-Host "== SUMMARY HTML (first lines) ==" -ForegroundColor Yellow
Get-Content $Summary | Select-Object -First 10

Write-Host "[OK]   Smoke/export completed" -ForegroundColor Green

