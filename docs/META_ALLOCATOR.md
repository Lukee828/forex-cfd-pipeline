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


Local:
  pwsh tools/Run-MetaAllocator.ps1
  pwsh tools/Export-Allocations.ps1
CI:
  gh workflow run .github/workflows/ci-meta.yml --ref main

  ### Meta Allocator Smoke (dispatch)
Run manually:
```powershell
gh workflow run .github/workflows/meta-alloc-smoke.yml

### Meta Allocator smoke (manual)
```powershell
$wf = '.github/workflows/meta-alloc-smoke.yml'
gh workflow run $wf
$rid = gh run list --workflow $wf -L 1 --json databaseId --jq '.[0].databaseId'
gh run download $rid --name allocations --dir "artifacts/ci-meta/$rid"