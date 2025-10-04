param(
  [string]$Cfg = "config/production.yaml",
  [string]$Start = "",
  [string]$End = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Ensure-Python {
  $py = ".\.venv\Scripts\python.exe"
  if (-not (Test-Path $py)) {
    Write-Host "Creating .venv (trying Python 3.11 first) ..."
    try { py -3.11 -m venv .venv } catch { py -m venv .venv }
  }
  return ".\.venv\Scripts\python.exe"
}

function Ensure-Deps([string]$py) {
  & $py -m pip install -U pip | Out-Null
  if (Test-Path ".\requirements.txt") {
    Write-Host "Installing dependencies from requirements.txt ..."
    & $py -m pip install -r .\requirements.txt | Out-Null
  } else {
    Write-Host "No requirements.txt found — skipping deps install."
  }
}

# 1) Env
$py = Ensure-Python
Ensure-Deps $py

# 2) Build args
$argsList = @('-m','src.exec.backtest','--cfg', $Cfg)
if ($Start) { $argsList += @('--start', $Start) }
if ($End)   { $argsList += @('--end',   $End)   }
if ($DryRun){ $argsList += '--dry-run' }

# 3) Run
Write-Host "Running: $($py) $($argsList -join ' ')"
& $py @argsList
if ($LASTEXITCODE -ne 0) { throw "Backtest failed (exit $LASTEXITCODE)" }

# 4) Friendly summary
$lastRun = Get-ChildItem -Directory .\runs\backtest_* -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 1
if ($lastRun) {
  Write-Host "✔ Backtest done. Latest run dir:" ($lastRun.FullName)
  $eq = Join-Path $lastRun.FullName 'equity.csv'
  if (Test-Path $eq) {
    $tail = (Get-Content $eq | Select-Object -Last 2) -join "`n"
    Write-Host "Equity (tail):`n$tail"
  }
} else {
  if ($DryRun) {
    Write-Host "✔ Dry run complete (no outputs written)."
  } else {
    Write-Host "ℹ No run dir found (did code skip writing outputs?)."
  }
}
