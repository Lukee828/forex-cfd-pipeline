param(
  [Parameter(Mandatory)]
  [string]$Symbols,
  [int]$FastMin, [int]$FastMax, [int]$FastStep,
  [int]$SlowMin, [int]$SlowMax, [int]$SlowStep,
  [int]$Steps,
  [int]$TradingBps = 0,   # default so it always has a value
  [string]$Parquet = "data",
  [switch]$Publish,
  [string]$Tag
)

$ErrorActionPreference = "Stop"
$venvPy = ".\.venv\Scripts\python.exe"

# Robust script directory (works even if PSCommandPath is null)
$scriptDir = if ($PSScriptRoot) {
  $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
  Split-Path -Path $MyInvocation.MyCommand.Path -Parent
} else {
  (Get-Location).Path
}

function Normalize-Equity {
  param([Parameter(Mandatory=$true)][string]$CsvPath)
  $code = @"
import pandas as pd, numpy as np, sys
p=sys.argv[1]
df = pd.read_csv(p, parse_dates=[0], index_col=0)
s = df.iloc[:,0].astype(float)
x = s.dropna()
near_one = (x.size>0) and (np.median(np.abs(x-1.0))<0.25) and (x.min()>0)
looks_ret = (x.size>0) and (x.abs().median()<0.02) and (x.abs().max()<0.5)
if looks_ret and not near_one:
    s = (1.0 + s.clip(-0.95,0.95)).cumprod()
s = s.replace([np.inf,-np.inf], np.nan).ffill().bfill()
start = float(s.iloc[0]) if len(s) else 1.0
floor = max(1e-8, 1e-6*start if start>0 else 1e-8)
s = s.clip(lower=floor)
s.to_frame("equity").to_csv(p)
"@
  & $venvPy -c $code $CsvPath | Out-Null
}

$gridRoot = Join-Path "runs" ("ma_grid_{0}" -f (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Force -Path $gridRoot | Out-Null

Write-Host "▶ Running MA grid ..." -ForegroundColor Cyan

for ($slow = $SlowMin; $slow -le $SlowMax; $slow += $SlowStep) {
  for ($fast = $FastMin; $fast -le $FastMax; $fast += $FastStep) {

    Write-Host ("  • fast={0}, slow={1}" -f $fast, $slow)

    $argsList = @(
      "-m","src.exec.backtest_event",
      "--symbols",$Symbols,
      "--strategy","ma_cross",
      "--fast",$fast,"--slow",$slow,
      "--max-steps",$Steps,
      "--parquet",$Parquet
    )
    # append trading-bps only if supplied
    if ($null -ne $TradingBps -and $TradingBps -is [int]) {
      $argsList += @("--trading-bps", $TradingBps)
    }

    $out = & $venvPy @argsList 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Host ""
      Write-Host ("❌ Python failed for fast={0} slow={1} (exit {2}). Log tail:" -f $fast,$slow,$LASTEXITCODE) -ForegroundColor Red
      ($out | Select-Object -Last 15) | ForEach-Object { "  $_" }
      throw "Backtest failed for fast=$fast slow=$slow"
    }

    $comboDir = Join-Path $gridRoot ("fast{0}_slow{1}" -f $fast,$slow)
    New-Item -ItemType Directory -Force -Path $comboDir | Out-Null

    # Prefer single-run equity, then event equity
    $srcCandidates = @(
      (Join-Path 'runs' 'equity.csv'),
      (Join-Path 'runs' 'event_equity.csv')
    )
    $src = $null
    foreach ($cand in $srcCandidates) { if (Test-Path $cand) { $src = $cand; break } }
    if (-not $src) { Write-Warning "    (no equity file found - skipped)"; continue }

    # Copy equity and normalize
    $dst = Join-Path $comboDir "equity.csv"
    Copy-Item $src $dst -Force
    Normalize-Equity -CsvPath $dst

    # Also copy positions if present (for cost application in summarizer)
    $posSrc = Join-Path 'runs' 'positions.csv'
    if (Test-Path $posSrc) {
      Copy-Item $posSrc (Join-Path $comboDir 'positions.csv') -Force
    }

    "fast=$fast slow=$slow" | Set-Content (Join-Path $comboDir "meta.txt") -Encoding UTF8

    # Clean residue so next loop can't be poisoned
    Get-ChildItem runs -Filter "*equity*.csv" -ErrorAction SilentlyContinue | Remove-Item -ErrorAction SilentlyContinue
    Remove-Item (Join-Path 'runs' 'positions.csv') -ErrorAction SilentlyContinue
  }
}

Write-Host "`nSummarizing..." -ForegroundColor Yellow
$sumPath = Join-Path $scriptDir 'Summarize-Grid.py'
if (-not (Test-Path $sumPath)) { throw "Missing tools/Summarize-Grid.py (expected at: $sumPath)." }

# Use the user-specified TradingBps for summary too
& $venvPy $sumPath --grid "$gridRoot" --trading-bps $TradingBps
if ($LASTEXITCODE -ne 0) { throw "Summary failed" }

Write-Host "`nOutputs: $gridRoot" -ForegroundColor Green
Get-ChildItem $gridRoot | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize

if ($Publish) {
  if (-not $Tag) { throw "Provide -Tag when using -Publish" }
  $pubScript = Join-Path $scriptDir 'Publish-Release.ps1'
  if (-not (Test-Path $pubScript)) { throw "Missing tools/Publish-Release.ps1 (expected at: $pubScript)" }
  pwsh -File $pubScript -Tag $Tag -RunPath $gridRoot
}
