param(
  [double]$Price,
  [double]$Equity,
  [double]$VolTargetAnnual = 0.20,
  [int]$VolWindow = 30,
  [double]$VolMinScale = 0.25,
  [double]$VolMaxScale = 1.0,
  [int]$DDWindow = 100,
  [double]$MaxDD = 0.20,
  [double]$DDFloor = 0.25
)
$py = @"
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer
p = GovernorParams(
    vol_target_annual=$VolTargetAnnual,
    vol_window=$VolWindow,
    vol_min_scale=$VolMinScale,
    vol_max_scale=$VolMaxScale,
    dd_window=$DDWindow,
    max_drawdown=$MaxDD,
    dd_floor_scale=$DDFloor,
)
g = RiskGovernedSizer(p)
scale, info = g.step($Price, $Equity)
print(f"scale={scale:.6f}")
for k,v in sorted(info.items()):
    print(f"{k}={v}")
"@
$tmp = Join-Path $env:TEMP ("rg_step_" + [guid]::NewGuid().ToString("N") + ".py")
Set-Content -LiteralPath $tmp -Value $py -Encoding UTF8
try {
  $env:PYTHONPATH = "$PWD;$PWD\src"
  & .\.venv\Scripts\python.exe $tmp
} finally {
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
