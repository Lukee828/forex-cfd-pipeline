param(
  [Parameter(Mandatory)]
  [string] $GridPath,

  # Accepts 0,2,5 or @(0,2,5) or '0,2,5'
  [object] $Bps = @(0,2,5)
)

$ErrorActionPreference = 'Stop'
$py = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $GridPath)) { throw "GridPath not found: $GridPath" }

# --- normalize BPS into a flat int[] ---
$flat = @()
foreach ($x in @($Bps)) {
  if ($x -is [System.Array]) { $flat += $x } else { $flat += $x }
}
$flat = $flat | ForEach-Object { [int]$_ } | Select-Object -Unique | Sort-Object

foreach ($bps in $flat) {
  Write-Host "Summarizing @ $bps bps..." -ForegroundColor Yellow
  & $py tools/Summarize-Grid.py --grid "$GridPath" --trading-bps $bps
  if ($LASTEXITCODE -ne 0) { throw "Summarize-Grid failed for bps=$bps" }

  $base = Join-Path $GridPath 'summary.csv'
  $out  = Join-Path $GridPath ("summary_bps{0}.csv" -f $bps)
  if (Test-Path $base) {
    Move-Item $base $out -Force
    Write-Host "  -> $out" -ForegroundColor Green
  } else {
    Write-Warning "  (no summary.csv produced at bps=$bps)"
  }
}

# Pretty print top-5 per BPS
foreach ($bps in $flat) {
  $csv = Join-Path $GridPath ("summary_bps{0}.csv" -f $bps)
  if (-not (Test-Path $csv)) { continue }
  Write-Host ""
  Write-Host "Top 5 @ ${bps} bps" -ForegroundColor Cyan
  Import-Csv $csv |
    Sort-Object { [double]($_.Sharpe -replace ',','.') } -Descending |
    Select-Object -First 5 fast,slow,Total,CAGR,Vol,Sharpe,Sortino,Calmar,MaxDD,WinRate,Trades |
    Format-Table -AutoSize
}
