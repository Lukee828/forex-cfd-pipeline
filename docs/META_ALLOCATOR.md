# Meta Allocator (Milestone 4)

A lightweight allocator that blends sleeves with EWMA scoring, a correlation governor, and a turnover penalty.

## Interfaces

- `AllocatorConfig`: mode (`"ewma"`/`"bayesian"`), bounds, EWMA alpha, correlation cap/strength, turnover penalty.
- `MetaAllocator.allocate(metrics, prev_weights=None, corr=None) -> dict[str,float]`
    - `metrics`: per-sleeve dicts with keys like `sharpe`, `dd`, optional `prev_score`.
    - `prev_weights`: previous allocation to penalize turnover.
    - `corr`: pairwise correlation map (symmetric).

## Notes

- This is infra-ready and testable; extend `_score_bayesian` later (conformal / BOCPD gating).
- Correlation governor dampens both sleeves above `corr_cap` with linear strength.
- Turnover penalty shrinks moves by `lam * |w - prev|`.
