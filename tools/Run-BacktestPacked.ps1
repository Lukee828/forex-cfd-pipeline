Param(
  [Parameter(Mandatory=$true)][string]$Pair,
  [Parameter(Mandatory=$true)][string]$TF,
  [Parameter(Mandatory=$true)][string]$Start,  # YYYY-MM-DD
  [Parameter(Mandatory=$true)][string]$End,    # YYYY-MM-DD
  [ValidateSet("mr","breakout")][string]$Strategy = "mr"
)
$ErrorActionPreference = "Stop"

$Py = ".venv/Scripts/python.exe"; if (-not (Test-Path $Py)) { $Py = "python" }
$old = $env:PYTHONPATH; $env:PYTHONPATH = "$PWD;$PWD\src"
$env:DUKASCOPY_OFFLINE = "1"
try {
  # 1) Run your existing CLI (flat artifacts writer)
  & $Py -m src.backtest.cli --pair $Pair --tf $TF --start $Start --end $End --strategy $Strategy

  # 2) Re-pack artifacts into structured folder
  $pairKey = $Pair
  $tfKey   = $TF
  $startKey = $Start -replace "-",""
  $endKey   = $End   -replace "-",""
  $runKey  = '{0}_{1}_{2}_{3}' -f $pairKey, $tfKey, $startKey, $endKey
$dstBase = Join-Path -Path 'artifacts/backtests' -ChildPath $runKey
$dst     = Join-Path -Path $dstBase -ChildPath $Strategy
  $runKey  = '{0}_{1}_{2}_{3}' -f $pairKey, $tfKey, $startKey, $endKey
$dstBase = Join-Path -Path 'artifacts/backtests' -ChildPath $runKey
$dst     = Join-Path -Path $dstBase -ChildPath $Strategy
  if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }

  $eq = "artifacts/equity.csv"
  $pn = "artifacts/pnl.csv"
  $sj = "artifacts/summary.json"
  if (Test-Path $eq) { Copy-Item -Force $eq (Join-Path $dst "equity.csv") }
  if (Test-Path $pn) { Copy-Item -Force $pn (Join-Path $dst "pnl.csv") }
  if (Test-Path $sj) { Copy-Item -Force $sj (Join-Path $dst "summary.json") }

  Write-Host ("Packed into: " + $dst)
  if (Test-Path (Join-Path $dst "summary.json")) {
    Write-Host "summary.json:" -ForegroundColor Cyan
    Get-Content (Join-Path $dst "summary.json")
  }
} finally {
  $env:PYTHONPATH = $old
}

