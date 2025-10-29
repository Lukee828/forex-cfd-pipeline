from __future__ import annotations
from typing import Mapping, TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    import pandas as pd

from .alloc_io import apply_meta_weights


def clip_exposure(x: "pd.Series", cap: float = 1.0) -> "pd.Series":
    """Clip combined sleeve exposure into [-cap, cap]."""

    cap = float(cap)
    if cap <= 0:
        raise ValueError("cap must be > 0")
    return x.clip(lower=-cap, upper=cap)


def distribute_across_assets(
    exposure: "pd.Series",
    assets: Sequence[str],
    per_asset_cap: float = 0.5,
) -> "pd.DataFrame":
    """
    Split a single combined exposure across assets equally,
    cap each asset to |per_asset_cap|, and ensure gross per-row <= 1.0.
    """
    import pandas as pd

    if not assets:
        raise ValueError("No assets provided.")
    df = pd.DataFrame(index=exposure.index, columns=list(assets), dtype=float)
    n = float(len(assets))
    per_asset_cap = float(per_asset_cap)
    if per_asset_cap <= 0:
        raise ValueError("per_asset_cap must be > 0")

    # Equal split, then per-asset cap, then (soft) renormalize if gross > 1
    for ts, v in exposure.items():
        row = [float(v) / n for _ in assets]
        # per-asset cap
        row = [max(min(x, per_asset_cap), -per_asset_cap) for x in row]
        gross = sum(abs(x) for x in row)
        if gross > 1.0 and gross > 0:
            # scale down to keep gross at 1.0
            scale = 1.0 / gross
            row = [x * scale for x in row]
        df.loc[ts] = row
    return df


def to_targets(
    per_sleeve_signals: Mapping[str, "pd.Series"],
    alloc_weights: Mapping[str, float],
    assets: Sequence[str],
    cap_exposure: float = 1.0,
    per_asset_cap: float = 0.5,
) -> "pd.DataFrame":
    """
    Combine sleeve signals with allocation weights, clip to cap_exposure,
    and distribute across assets with per-asset cap. Returns DataFrame
    indexed by time, columns = assets, values in [-per_asset_cap, +per_asset_cap].
    """

    combo = apply_meta_weights(per_sleeve_signals, alloc_weights)
    combo = clip_exposure(combo, cap=cap_exposure)
    return distribute_across_assets(combo, assets=assets, per_asset_cap=per_asset_cap)


__all__ = ["clip_exposure", "distribute_across_assets", "to_targets"]
