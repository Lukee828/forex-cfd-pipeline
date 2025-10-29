from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping


@dataclass(frozen=True)
class Allocation:
    weights: Dict[str, float]


def _read_csv(p: Path) -> Dict[str, float]:
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return {}
    # Expect header: Sleeve,Weight
    rows = lines[1:] if "Sleeve" in lines[0] else lines
    out: Dict[str, float] = {}
    for r in rows:
        parts = [x.strip() for x in r.split(",")]
        if len(parts) < 2:
            continue
        k, v = parts[0], float(parts[1])
        out[k] = v
    return out


def validate_alloc(w: Mapping[str, float], eps: float = 1e-6) -> None:
    if not w:
        raise ValueError("No allocation weights found.")
    for k, v in w.items():
        if not (0.0 - eps) <= float(v) <= (1.0 + eps):
            raise ValueError(f"Weight out of range for {k}: {v}")
    s = sum(float(v) for v in w.values())
    if abs(s - 1.0) > 1e-4:
        raise ValueError(f"Weights do not sum to 1.0 (sum={s:.6f})")


def _latest_csv(dirpath: Path) -> Path | None:
    latest = dirpath / "latest.csv"
    if latest.exists():
        return latest
    # fallback: pick the newest *_alloc.csv by name
    cand = sorted(dirpath.glob("*_alloc.csv"))
    return cand[-1] if cand else None


def load_latest_alloc(dirpath: str | Path = "artifacts/allocations") -> Allocation:
    d = Path(dirpath)
    p = _latest_csv(d)
    if p is None:
        raise FileNotFoundError(f"No allocation CSVs in {d}")
    weights = _read_csv(p)
    validate_alloc(weights)
    return Allocation(weights=weights)


def apply_meta_weights(per_sleeve_signals: Mapping[str, "pd.Series"], weights: Mapping[str, float]):
    """
    Combine per-sleeve signed signals (or target exposures) with allocation weights.
    Assumes each series is already in [-1, +1] or desired units.
    Returns a single combined series aligned to the union index.
    """
    import pandas as pd

    if not per_sleeve_signals:
        raise ValueError("No sleeve signals provided.")
    validate_alloc(weights)

    # Union index across series
    idx = None
    for s in per_sleeve_signals.values():
        idx = s.index if idx is None else idx.union(s.index)

    out = pd.Series(0.0, index=idx)
    for k, s in per_sleeve_signals.items():
        w = float(weights.get(k, 0.0))
        if w == 0.0:
            continue
        out = out.add(s.reindex(idx).fillna(0.0) * w, fill_value=0.0)
    return out
