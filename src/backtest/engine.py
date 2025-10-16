from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np, pandas as pd
from src.runtime.risk_governed import GovernorParams, RiskGovernedSizer

@dataclass
class Costs:
    bps: float = 5.0

def run_backtest(df: pd.DataFrame, signals: pd.Series, costs: Costs = Costs()) -> Dict[str, Any]:
    df = df.copy()
    sig = signals.reindex(df.index).fillna(0.0).astype(float)
    ret = df["close"].pct_change().fillna(0.0)
    # position = signal (unit), scaled by RiskGovernor
    eq = 100000.0
    rp = GovernorParams()
    rg = RiskGovernedSizer(rp)
    positions = []
    scales = []
    equity = []
    for i,(t,r) in enumerate(zip(df.index, ret.values)):
        eq *= (1.0 + (sig.iat[i] * r))
        scale, info = rg.step(float(df["close"].iat[i]), float(eq))
        positions.append(sig.iat[i] * scale)
        scales.append(scale)
        equity.append(eq)
    # simple costs on turnover
    pos = pd.Series(positions, index=df.index)
    turnover = pos.diff().abs().fillna(0.0)
    cost = turnover * (costs.bps/10000.0)
    pnl = (pos.shift(1).fillna(0.0) * ret) - cost
    curve = (1.0 + pnl).cumprod()
    out = {
        "equity_curve": curve,
        "pnl": pnl,
        "turnover": turnover,
        "summary": {
            "ret": float(curve.iat[-1]-1.0 if len(curve) else 0.0),
            "vol": float(np.std(pnl.values)*np.sqrt(252)),
        }
    }
    return out
