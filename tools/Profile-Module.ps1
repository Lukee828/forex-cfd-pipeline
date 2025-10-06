param(
  [Parameter(Mandatory=$true)][string]$Target,   # e.g. src.exec.backtest:main
  [string]$ArgsJson = "[]",
  [string]$KwargsJson = "{}",
  [string]$Out = "profile.stats",
  [int]$Top = 30
)

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

& $py tools/Profile-Run.py --target $Target --args $ArgsJson --kwargs $KwargsJson --out $Out --top $Top
if ($LASTEXITCODE -ne 0) { throw "Profiling failed." }

Write-Host "[OK] Wrote CPU profile -> $Out" -ForegroundColor Green
