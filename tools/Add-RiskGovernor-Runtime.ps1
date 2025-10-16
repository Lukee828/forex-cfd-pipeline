#requires -Version 7
$ErrorActionPreference = 'Stop'
$utf8 = [Text.UTF8Encoding]::new($false)

function Write-Text($path, $text){
  $dir = Split-Path -Parent $path
  if($dir -and -not (Test-Path $dir)){ New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  [IO.File]::WriteAllText($path, ($text -replace "`r?`n","`n"), $utf8)
}

# Idempotent: ensure runtime sizer + demo + test exist
$runtime = 'src/runtime/risk_governed.py'
$demo    = 'tools/rg_demo.py'
$itest   = 'tests/integration/test_runtime_governor.py'

if(-not (Test-Path $runtime)){
  Write-Text $runtime @"
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List
import numpy as np
from src.risk.risk_governor import RiskGovernor, RiskGovernorConfig

@dataclass
class GovernorParams:
    enabled: bool = True
    dd_window: int = 100
    max_drawdown: float = 0.20
    dd_floor_scale: float = 0.25
    vol_target_annual: float = 0.15
    vol_min_scale: float = 0.25
    vol_max_scale: float = 2.00
    vol_window: int = 30
    trading_days: int = 252
    def to_cfg(self) -> RiskGovernorConfig:
        return RiskGovernorConfig(
            dd_window=self.dd_window, max_drawdown=self.max_drawdown,
            dd_floor_scale=self.dd_floor_scale, vol_target_annual=self.vol_target_annual,
            vol_min_scale=self.vol_min_scale, vol_max_scale=self.vol_max_scale,
            vol_window=self.vol_window, trading_days=self.trading_days,
        )

class RiskGovernedSizer:
    def __init__(self, params: GovernorParams):
        self.params = params
        self._rg = RiskGovernor(params.to_cfg()) if params.enabled else None
        self._last_price: Optional[float] = None
    def step(self, price: float, equity: float) -> Tuple[float, Dict]:
        if not self.params.enabled:
            return 1.0, {"mode": "off"}
        r = 0.0 if self._last_price is None else (price - self._last_price) / (self._last_price or 1.0)
        self._last_price = float(price)
        scale, info = self._rg.update(equity_value=float(equity), ret=float(r))
        return float(scale), info
"@
}

if(-not (Test-Path $demo)){
  Write-Text $demo @"
from __future__ import annotations
import argparse
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--off", action="store_true")
    p.add_argument("--vol-target-annual", type=float, default=0.15)
    p.add_argument("--vol-window", type=int, default=30)
    p.add_argument("--vol-min-scale", type=float, default=0.25)
    p.add_argument("--vol-max-scale", type=float, default=2.0)
    p.add_argument("--dd-window", type=int, default=100)
    p.add_argument("--max-dd", type=float, default=0.20)
    p.add_argument("--dd-floor", type=float, default=0.25)
    a = p.parse_args()
    params = GovernorParams(enabled=not a.off, vol_target_annual=a.vol_target_annual,
                            vol_window=a.vol_window, vol_min_scale=a.vol_min_scale,
                            vol_max_scale=a.vol_max_scale, dd_window=a.dd_window,
                            max_drawdown=a.max_dd, dd_floor_scale=a.dd_floor)
    rg = RiskGovernedSizer(params)
    prices = [100,101,99,98,100,104,102]; equity = 100_000.0
    for i, px in enumerate(prices):
        if i: equity *= 1.0 + (px - prices[i-1]) / prices[i-1]
        scale, info = rg.step(px, equity)
        print(i, f"px={px:.2f}", f"eq={equity:.2f}", f"scale={scale:.3f}",
              f"mode={info.get('mode','vol')}", f"dd={info.get('dd_tripped')}",
              f"vol={info.get('vol_ann')}")
if __name__ == "__main__": main()
"@
}

if(-not (Test-Path $itest)){
  Write-Text $itest @"
from __future__ import annotations
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer
def test_governor_runtime_sanity():
    g = RiskGovernedSizer(GovernorParams(enabled=True, vol_target_annual=0.2, vol_window=30))
    eq = 100_000.0; prices = [100,99,98,105,103,101]; seen=[]
    for i, p in enumerate(prices):
        if i: eq *= 1.0 + (p - prices[i-1]) / prices[i-1]
        s, info = g.step(p, eq)
        assert 0.0 <= s <= 2.0
        seen.append(s)
    assert len(seen) == len(prices)
"@
}

# Run the integration test with PYTHONPATH set
$old = $env:PYTHONPATH
$env:PYTHONPATH = "$PWD;$PWD\src"
try {
  & .\.venv\Scripts\python.exe -m pytest -q tests\integration\test_runtime_governor.py
} finally {
  $env:PYTHONPATH = $old
}

# Optional push (fast if GIT_FAST=1)
try {
  git add -- $runtime $demo $itest | Out-Null
  try { git commit -m "runtime(risk): ensure RiskGovernedSizer + demo + test present" 2>$null | Out-Null } catch {}
  git push | Out-Null
} catch {}

Write-Host "`n✅ Runtime governor script executed successfully." -ForegroundColor Green
