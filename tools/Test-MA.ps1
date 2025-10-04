param(
  [string]$Symbols = "EURUSD,GBPUSD,USDJPY,XAUUSD",
  [int]$Fast = 20,
  [int]$Slow = 100,
  [int]$Steps = 500,
  [string]$Parquet = "data"
)

$ErrorActionPreference = "Stop"
$venvPy = ".\.venv\Scripts\python.exe"

$argsList = @(
  "-m","src.exec.backtest_event",
  "--symbols",$Symbols,
  "--strategy","ma_cross",
  "--fast",$Fast,"--slow",$Slow,
  "--max-steps",$Steps,
  "--parquet",$Parquet
)

Write-Host "▶ Running MA Cross (fast=$Fast, slow=$Slow) ..."
& $venvPy @argsList
if ($LASTEXITCODE -ne 0) { throw "Backtest failed (exit $LASTEXITCODE)" }
