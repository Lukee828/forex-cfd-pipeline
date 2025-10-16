from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import pandas as pd

# Optional risk imports (soft-fail)
try:
    from src.risk.spread_guard import SpreadGuardConfig, check_spread_ok  # type: ignore
except Exception:
    SpreadGuardConfig = None  # type: ignore
    check_spread_ok = None  # type: ignore

from ._compat_risk import new_spread_guard_config

try:
    from src.risk.vol_state import VolStateMachine, infer_vol_regime  # type: ignore
except Exception:
    VolStateMachine = None  # type: ignore
    infer_vol_regime = None  # type: ignore

try:
    from src.risk.risk_governor import RiskGovernor, RiskGovernorConfig  # type: ignore
except Exception:
    RiskGovernor = None  # type: ignore
    RiskGovernorConfig = None  # type: ignore


@dataclass
class RiskInputs:
    pair: str
    spread_bps: float
    window: int = 20


def gather_risk_features(inp: RiskInputs) -> Dict[str, Any]:
    snap: Dict[str, Any] = {
        "pair": inp.pair,
        "ts": datetime.now(timezone.utc).isoformat(),
        "spread_bps": float(inp.spread_bps),
            "sg_spread_bps": float(inp.spread_bps),
    }

    # SpreadGuard (if available)
    if SpreadGuardConfig and check_spread_ok:
        try:
            cfg = new_spread_guard_config(SpreadGuardConfig, max_spread_bps=25.0)  # compat: helper that expects the class
        except TypeError:
            cfg = new_spread_guard_config(max_spread_bps=25.0)  # compat: helper that builds internally
        try:
            snap["spread_ok"] = bool(check_spread_ok(float(inp.spread_bps), cfg))
        except Exception:
            snap["spread_ok"] = None
    else:
        snap["spread_ok"] = None

    # Vol regime (if available)
    if VolStateMachine and infer_vol_regime:
        try:
            snap["vol_regime"] = infer_vol_regime([])
        except Exception:
            snap["vol_regime"] = None
    else:
        snap["vol_regime"] = None

    # RiskGovernor (if available)
    if RiskGovernor and RiskGovernorConfig:
        try:
            rg = RiskGovernor(RiskGovernorConfig())
            scale, info = rg.scale()
            snap.update({
                "rg_scale": float(scale),
                "rg_mode": info.get("mode", "vol"),
                "rg_dd_tripped": bool(info.get("dd_tripped", False)),
                "rg_vol_ann": float(info.get("vol_ann", 0.0) or 0.0),
            })
        except Exception:
            snap.update({k: None for k in ("rg_scale","rg_mode","rg_dd_tripped","rg_vol_ann")})
    else:
        snap.update({k: None for k in ("rg_scale","rg_mode","rg_dd_tripped","rg_vol_ann")})

    return snap


def export_risk_snapshot(inp: RiskInputs, db_path: Optional[str] = None, table: str = 'risk_snapshots') -> str:
    df = pd.DataFrame([gather_risk_features(inp)])

    if not db_path:
        return table

    try:
        import duckdb  # type: ignore
        con = duckdb.connect(db_path)
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0;")
        con.execute(f"INSERT INTO {table} SELECT * FROM df")
        con.close()
        return table
    except Exception:
        # no duckdb (or failed) — still return table name for callers
        return table