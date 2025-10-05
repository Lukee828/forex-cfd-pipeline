param(
  [string]$Cfg = "config\\example.yaml",
  [string]$Python = ".\\.venv\\Scripts\\python.exe"
)
$ErrorActionPreference = "Stop"

# Run as a module so the 'src' package is authoritative
$out = & $Python -m src.exec.backtest --cfg $Cfg --dry-run 2>&1
$txt = [string]::Join("`n",$out)

if ($txt -notmatch 'flags:\s+vol_targeting=.*cost_windows=.*spread_guard=.*dual_tp=.*time_stop=.*be_gate_opposite=.*') {
  $out | Select-Object -First 60 | Write-Host
  throw "Flag print diagnostic not found in output."
}

Write-Host "Flag print OK ✅" -ForegroundColor Green
