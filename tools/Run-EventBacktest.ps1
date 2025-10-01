[CmdletBinding()]
param(
  [string]$Cfg = "config/production.yaml",
  [string]$Start = "",
  [string]$End   = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo   = (Resolve-Path ".").Path
$venvPy = Join-Path $repo ".venv\Scripts\python.exe"

# Ensure venv exists
if (!(Test-Path $venvPy)) {
  Write-Host "Creating .venv (Python 3.11 preferred) ..."
  try { py -3.11 -m venv .venv } catch { py -m venv .venv }
}

# Upgrade pip quickly
& $venvPy -m pip install -U pip | Out-Host

# Install deps (requirements.txt if present, else minimal)
if (Test-Path "$repo\requirements.txt") {
  & $venvPy -m pip install -r "$repo\requirements.txt" | Out-Host
} else {
  & $venvPy -m pip install pandas pyarrow pyyaml matplotlib | Out-Host
}

# Compose args for your backtester
$argsList = @("-m","src.exec.backtest","--cfg",$Cfg)
if ($Start) { $argsList += @("--start",$Start) }
if ($End)   { $argsList += @("--end",$End) }
if ($DryRun) { $argsList += @("--dry-run") }

# Log output
$logDir  = Join-Path $repo "runs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "last_backtest.log"

Write-Host "Running: $venvPy $($argsList -join ' ')"
& $venvPy @argsList *>&1 | Tee-Object -FilePath $logPath
exit $LASTEXITCODE
