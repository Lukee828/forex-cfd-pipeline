param(
  [string]$RunsDir = ".\runs",
  [switch]$OpenChart,   # open equity.png if found
  [switch]$OpenFolder   # open the latest run folder in Explorer
)

$ErrorActionPreference = "Stop"
Write-Host "▶ Starting day at $(Get-Date)" -ForegroundColor Cyan

# 1) Git status
Write-Host "`n=== Git Status ===" -ForegroundColor Yellow
git log -1 --oneline
git status -s

# 2) Latest run folder
$last = $null
if (Test-Path $RunsDir) {
  $last = Get-ChildItem $RunsDir -Directory -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

if ($last) {
  Write-Host "`n=== Latest Run: $($last.Name) ===" -ForegroundColor Yellow
  Get-ChildItem $last.FullName | Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize

  $equityCsv = Join-Path $last.FullName "equity.csv"
  if (Test-Path $equityCsv) {
    Write-Host "`nEquity sample:" -ForegroundColor Yellow
    Get-Content $equityCsv -Head 5
    Get-Content $equityCsv -Tail 5
  }

  # 3) Optional open actions
  if ($OpenChart) {
    $png = Join-Path $last.FullName "equity.png"
    if (Test-Path $png) {
      Write-Host "`nOpening chart: $png" -ForegroundColor Green
      Start-Process $png
    } else {
      Write-Host "`n(no equity.png found to open)" -ForegroundColor DarkYellow
    }
  }

  if ($OpenFolder) {
    Write-Host "Opening folder: $($last.FullName)" -ForegroundColor Green
    Start-Process $last.FullName
  }
} else {
  Write-Host "`n(no runs found under $RunsDir)" -ForegroundColor DarkYellow
}

# 4) Suggestions
Write-Host "`n=== Next Step Suggestion ===" -ForegroundColor Yellow
Write-Host "👉 Extend grid reporting (CSV → summary metrics + charts)"
Write-Host "👉 Hook OB-ZigZag strategy into engine"
Write-Host "👉 Automate one-shot Run → Summarize → Publish"
