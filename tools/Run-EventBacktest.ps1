<#  Run-EventBacktest.ps1
    Minimal, one-shot runner for the event-driven backtester.

    What it does:
      - Finds/creates a local venv (.venv) using Python 3.11+ if available
      - Installs requirements.txt (if present)
      - Runs the backtester entrypoint with overridable params
      - Logs stdout/stderr to runs\last_backtest.log

    Usage examples:
      # vanilla run
      powershell -ExecutionPolicy Bypass -File tools\Run-EventBacktest.ps1

      # custom symbols + out prefix
      powershell -ExecutionPolicy Bypass -File tools\Run-EventBacktest.ps1 -Symbols "EURUSD,GBPUSD,USDJPY" -OutPrefix "DEMO"

      # set explicit start/end (UTC dates)
      powershell -ExecutionPolicy Bypass -File tools\Run-EventBacktest.ps1 -Start "2022-01-01" -End "2024-01-01"
#>

[CmdletBinding()]
param(
  [string]$Symbols = "",                # comma-separated; empty = use defaults from config
  [string]$Start   = "",                # e.g. 2020-01-01
  [string]$End     = "",                # e.g. 2024-12-31
  [string]$OutPrefix = "NIGHTLY",       # results prefix
  [string]$Config    = "config/production.yaml",
  [switch]$DryRun                         # passthrough flag if your entrypoint supports it
)

$ErrorActionPreference = 'Stop'

function Find-Python {
  # Prefer specific 3.11 if installed, then fall back
  $candidates = @("py -3.11","py -3.12","py -3","python","python3")
  foreach ($c in $candidates) {
    try {
      $v = & $c -c "import sys;print(sys.version)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $v) { return $c }
    } catch {}
  }
  throw "Python not found. Please install Python 3.11+ and make it available on PATH."
}

function Ensure-Venv([string]$pyCmd) {
  $venvRoot = Join-Path $PSScriptRoot "..\.venv" | Resolve-Path -ErrorAction SilentlyContinue
  if (-not $venvRoot) {
    $venvRoot = Join-Path (Resolve-Path "$PSScriptRoot\..").Path ".venv"
  } else {
    $venvRoot = $venvRoot.Path
  }

  if (-not (Test-Path $venvRoot)) {
    Write-Host "Creating venv at $venvRoot ..."
    & $pyCmd -m venv $venvRoot
  }
  $venvPy = Join-Path $venvRoot "Scripts\python.exe"
  if (-not (Test-Path $venvPy)) {
    throw "Virtualenv looks broken: $venvPy not found."
  }
  return $venvPy
}

function Pip-Install([string]$venvPy, [string]$reqPath) {
  Write-Host "Upgrading pip..."
  & $venvPy -m pip install --upgrade pip
  if (Test-Path $reqPath) {
    Write-Host "Installing dependencies from $reqPath ..."
    & $venvPy -m pip install -r $reqPath
  } else {
    Write-Host "No requirements.txt found — skipping deps install."
  }
}

function Run-Backtest([string]$venvPy) {
  # Prefer module form: python -m src.exec.backtest ...
  $argsList = @("-m","src.exec.backtest","--config",$Config,"--out_prefix",$OutPrefix)

  if ($Symbols.Trim()) {
    # Many of your CLIs accept: --symbols EURUSD GBPUSD ...
    $symbolsArray = $Symbols.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $argsList += "--symbols"
    $argsList += $symbolsArray
  }
  if ($Start.Trim()) { $argsList += @("--start",$Start) }
  if ($End.Trim())   { $argsList += @("--end",$End) }
  if ($DryRun)       { $argsList += "--dry_run" }

  # Fallback to script path if the module import fails
  $logDir = "runs"
  if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
  $logPath = Join-Path $logDir "last_backtest.log"

  Write-Host "Running backtest: $($argsList -join ' ')"
  $env:PYTHONUTF8 = "1"

  # Try module call
  & $venvPy @argsList *>&1 | Tee-Object -FilePath $logPath
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Module run failed (exit $LASTEXITCODE). Trying direct script path fallback..."
    $scriptPath = "src\exec\backtest.py"
    if (-not (Test-Path $scriptPath)) {
      throw "Fallback script not found: $scriptPath"
    }
    & $venvPy $scriptPath @($argsList | Select-Object -Skip 2) *>&1 | Tee-Object -FilePath $logPath
    if ($LASTEXITCODE -ne 0) {
      throw "Backtest failed. Check log: $logPath"
    }
  }
  Write-Host "`n✅ Done. Log: $logPath"
}

# --- main ---
Push-Location (Resolve-Path "$PSScriptRoot\..").Path
try {
  $py = Find-Python
  $venvPy = Ensure-Venv $py

  $req = "requirements.txt"
  Pip-Install $venvPy $req

  Run-Backtest $venvPy
}
finally {
  Pop-Location
}
