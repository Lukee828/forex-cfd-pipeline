param(
  [string]$PythonExe = ".\.venv311\Scripts\python.exe",
  [string]$Db  = "$PWD\cli_smoke.duckdb",
  [string]$Csv = "$PWD\cli_best.csv",
  [string]$Html= "$PWD\cli_summary_dark.html"
)

$env:PYTHONPATH = (Resolve-Path .\src).Path
Remove-Item $Db,$Csv,$Html -ErrorAction SilentlyContinue

& $PythonExe -m alpha_factory.registry_cli --db $Db init
& $PythonExe -m alpha_factory.registry_cli --db $Db register --cfg h1 --metrics "sharpe=1.8" --tags demo
& $PythonExe -m alpha_factory.registry_cli --db $Db register --cfg h2 --metrics "sharpe=2.4" --tags demo
& $PythonExe -m alpha_factory.registry_cli --db $Db export --what best --metric sharpe --top 1 --format csv --out $Csv
& $PythonExe -m alpha_factory.registry_cli --db $Db export --what summary --metric sharpe --format html --theme dark --out $Html

if (-not (Test-Path $Csv))  { throw "best CSV not created: $Csv" }
if (-not (Test-Path $Html)) { throw "summary HTML not created: $Html" }

"== CSV head ==";  Get-Content $Csv  | Select-Object -First 2
"== HTML head =="; Get-Content $Html | Select-Object -First 3
Write-Host "[OK] CLI smoke passed" -ForegroundColor Green
