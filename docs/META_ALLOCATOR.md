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

$ErrorActionPreference='Stop'

$append = @"
## Meta Allocator — quick usage

**Local (writes timestamped CSV + \`latest.csv\`):**
```powershell
pwsh -File tools/Export-Allocations.ps1 -Mode ewma
# or: -Mode bayes | -Mode equal

$doc = "docs/META_ALLOCATOR.md"
$block = @"
## Meta Allocator — quick smoke

Local export (writes timestamped CSV + latest.csv):
```powershell
pwsh -File tools/Export-Allocations.ps1 -Mode ewma---

## PowerShell Tools & CI Smoke

This project ships PS7 helpers to exercise the Meta Allocator end-to-end (local CSVs + CI artifact):

### Export allocations (local)
```powershell
pwsh -File tools/Export-Allocations.ps1 -Mode ewma
pwsh -File tools/Export-Allocations.ps1 -Mode bayes
pwsh -File tools/Export-Allocations.ps1 -Mode equal
```

Writes:
- `artifacts/allocations/<YYYYMMDD_HHMMSS>_alloc.csv`
- `artifacts/allocations/latest.csv`

### Allocation report (delta vs previous)
```powershell
pwsh -File tools/Alloc-Report.ps1
```

### QA bundle (local export + CI dispatch + artifact fetch)
```powershell
pwsh -File tools/Alloc-QA.ps1 -Mode ewma
```

**CI workflow:** `.github/workflows/meta-alloc-smoke.yml` (manual `workflow_dispatch` only).

**Guards respected:** repository policy “no `push:` / no `pull_request_target:` triggers”.

**Notes:**
- CI sets `AF_SKIP_MT5=1` to avoid any MT5 side effects.
- CLI entrypoint: `src/alpha_factory/cli_meta_alloc.py`.
- Library: `src/alpha_factory/meta_allocator.py` (modes: `ewma`, `equal`, `bayes`).

