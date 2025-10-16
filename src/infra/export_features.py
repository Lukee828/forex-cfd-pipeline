from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import pandas as pd

from .registry import get_store, TABLES

# Optional imports; we keep integration soft so local dev never breaks.
try:
    from src.risk.spread_guard import SpreadGuardConfig, check_spread_ok  # type: ignore
from ._compat_risk import new_spread_guard_config
except Exception:  # pragma: no cover - optional
    SpreadGuardConfig = None  # type: ignore
    check_spread_ok = None  # type: ignore

try:
    from src.risk.vol_state import VolStateMachine, infer_vol_regime  # type: ignore
except Exception:  # pragma: no cover - optional
    VolStateMachine = None  # type: ignore
    infer_vol_regime = None  # type: ignore


@dataclass
class RiskInputs:
    pair: str
    spread_bps: float
    window: int = 20


def gather_risk_features(inp: RiskInputs) -> Dict[str, Any]:
    """Collect a minimal snapshot of risk features (gracefully downgrades if modules are missing)."""
    snap: Dict[str, Any] = {
        "pair": inp.pair,
        "ts": datetime.now(timezone.utc).isoformat(),
        "spread_bps": inp.spread_bps,
    }

    # SpreadGuard
    if SpreadGuardConfig and check_spread_ok:
        cfg = new_spread_guard_config(max_spread_bps=25.0)
        ok, bps = check_spread_ok(inp.spread_bps, cfg)
        snap["sg_ok"] = bool(ok)
        snap["sg_spread_bps"] = float(bps)
    else:
        snap["sg_ok"] = None
        snap["sg_spread_bps"] = None

    # Vol regime
    if VolStateMachine and infer_vol_regime:
        # Demo: infer with synthetic data (kept tiny for speed); real pipeline can pass true series
        regime = infer_vol_regime([0.01, 0.015, 0.02, 0.005, 0.012], lookback=inp.window)
        snap["vol_regime"] = str(regime)
    else:
        snap["vol_regime"] = None

    return snap


def export_risk_snapshot(inp: RiskInputs, db_path: Optional[str] = None) -> str:
    """Write one snapshot into DuckDB. Returns the table name used."""
    snap = gather_risk_features(inp)
    df = pd.DataFrame([snap])
    store = get_store(db_path)
    table = TABLES["risk_snapshots"]
    store.upsert_df(table, df)
    return table
