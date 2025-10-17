from __future__ import annotations
import os, csv, json, datetime as dt
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

import numpy as np

try:
    import pandas as pd  # optional at runtime
except Exception:  # pragma: no cover
    pd = None  # type: ignore

# Minimal adapters to the code you already have
from src.risk.risk_governor import RiskGovernor, RiskGovernorConfig

@dataclass
class Case:
    name: str
    prices: List[float]
    equity0: float = 100_000.0

@dataclass
class Result:
    name: str
    final_equity: float
    max_dd: float
    mean_scale: float
    sharpe: float

def run_case(c: Case) -> Result:
    rg = RiskGovernor(RiskGovernorConfig(vol_target_annual=0.2, vol_window=30))
    eq = float(c.equity0)
    scales: List[float] = []
    rets: List[float] = []
    max_peak = eq
    max_dd = 0.0
    for i, px in enumerate(c.prices):
        if i > 0:
            r = (px - c.prices[i-1]) / c.prices[i-1]
            rets.append(float(r))
            eq *= (1.0 + r)
            max_peak = max(max_peak, eq)
            dd = (max_peak - eq) / max(max_peak, 1e-12)
            max_dd = max(max_dd, dd)
        scale, info = rg.update(eq, 0.0 if i == 0 else rets[-1])
        scales.append(float(scale))
    # simple daily sharpe proxy
    sharpe = 0.0
    x = np.asarray(rets, dtype=float)
    if x.size > 1:
        mu = float(np.mean(x))
        sd = float(np.std(x, ddof=1))
        sharpe = float((mu / sd) * np.sqrt(252.0)) if sd > 0 else 0.0
    return Result(name=c.name, final_equity=float(eq), max_dd=float(max_dd),
                  mean_scale=float(np.mean(scales)), sharpe=float(sharpe))

def default_cases() -> List[Case]:
    rng = np.random.default_rng(7)
    base = 100.0
    a = [base]
    for _ in range(120):
        a.append(a[-1] * (1.0 + rng.normal(0.0003, 0.01)))
    b = [base]
    for _ in range(120):
        b.append(b[-1] * (1.0 + rng.normal(0.0, 0.02)))
    c = [base, 98, 96, 93, 110] + [110.5, 111.2, 108.0, 109.0, 111.0]
    return [Case("LOW_VOL", a), Case("HIGH_VOL", b), Case("WHIPSAW", c)]

def write_outputs(results: List[Result], outdir: str) -> Dict[str, str]:
    os.makedirs(outdir, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d")
    csv_path = os.path.join(outdir, f"regression-{ts}.csv")
    json_path = os.path.join(outdir, f"regression-{ts}.json")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    with open(json_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    # parquet (optional)
    parquet_path = ""
    if pd is not None:
        try:
            import pyarrow  # noqa: F401
            import pandas as pd2
            df = pd2.DataFrame([asdict(r) for r in results])
            parquet_path = os.path.join(outdir, f"regression-{ts}.parquet")
            df.to_parquet(parquet_path, index=False)
        except Exception:
            parquet_path = ""
    return {"csv": csv_path, "json": json_path, "parquet": parquet_path}

def main():
    cases = default_cases()
    results = [run_case(c) for c in cases]
    paths = write_outputs(results, "artifacts")
    print("wrote:", paths)

if __name__ == "__main__":
    main()
