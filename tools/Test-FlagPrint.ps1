param(
  [string]$Cfg = "config\\example.yaml",
  [string]$Python = ".\\.venv\\Scripts\\python.exe"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Python)) { throw "Python not found at $Python" }
if (-not (Test-Path $Cfg))    { throw "Config not found at $Cfg" }

# Run and capture stdout
$out = & $Python "src\\exec\\backtest.py" --cfg $Cfg --dry-run 2>&1
$outText = [string]::Join("`n", $out)

if ($outText -notmatch 'flags:\s+vol_targeting=.*cost_windows=.*spread_guard=.*dual_tp=.*time_stop=.*be_gate_opposite=.*') {
  Write-Host $outText
  throw "Flag print diagnostic not found in output."
}

Write-Host "Flag print OK ✅" -ForegroundColor Green
