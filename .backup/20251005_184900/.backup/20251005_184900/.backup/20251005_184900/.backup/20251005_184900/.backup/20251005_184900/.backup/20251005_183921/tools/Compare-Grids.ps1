param(
  [string]$RunsDir = "runs",
  [int]$MaxGrids = 12,
  [switch]$Plot,
  [int]$Top = 10
)

$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

# --- Run the Python analyzer ---
$argsList = @("tools/Compare-Grids.py", "--runs", $RunsDir, "--max-grids", $MaxGrids, "--top", $Top)
if ($Plot) { $argsList += "--plot" }
& $py @argsList

# --- Summaries from the generated CSVs ---
$combined = Join-Path $RunsDir "all_grids_combined.csv"
$stab     = Join-Path $RunsDir "grid_stability_by_bps.csv"
$cons     = Join-Path $RunsDir "best_params_consensus.csv"

if (Test-Path $cons) {
  Write-Host "`nTop consensus (robustness) — first $Top" -ForegroundColor Yellow
  Import-Csv $cons |
    Select-Object -First $Top `
      @{n='fast';e={[int]$_.fast}},
      @{n='slow';e={[int]$_.slow}},
      @{n='robust';e={ '{0:N2}' -f [double]($_.robust_score -replace ',','.') }},
      @{n='Sharpeμ';e={ '{0:N2}' -f [double]($_.sharpe_mean -replace ',','.') }},
      @{n='Sharpeσ';e={ '{0:N2}' -f [double]($_.sharpe_std  -replace ',','.') }},
      @{n='Calmarμ';e={ '{0:N2}' -f [double]($_.calmar_mean -replace ',','.') }},
      @{n='obs';e={ [int]$_.obs }} |
    Format-Table -AutoSize
}

if (Test-Path $stab) {
  Write-Host "`nPer-bps stability (top 10 by robust score)" -ForegroundColor Yellow
  Import-Csv $stab |
    Sort-Object { - [double]($_.robust_score -replace ',','.') } |
    Select-Object -First 10 fast,slow,
      @{n='bps';e={ if ($_.bps -eq ''){'NA'} else {[int]$_.bps} }},
      @{n='robust';e={ '{0:N2}' -f [double]($_.robust_score -replace ',','.') }},
      @{n='Sharpeμ';e={ '{0:N2}' -f [double]($_.sharpe_mean -replace ',','.') }},
      @{n='Sharpeσ';e={ '{0:N2}' -f [double]($_.sharpe_std  -replace ',','.') }},
      grids |
    Format-Table -AutoSize
}
