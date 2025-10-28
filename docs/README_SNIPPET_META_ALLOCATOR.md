## Meta Allocator — Quick Use (PS7 + CI)

Minimal allocator with three modes: `ewma` (default), `equal`, `bayes`.

### Local (write timestamped CSV + latest.csv)
```powershell
pwsh -File tools/Export-Allocations.ps1 -Mode ewma
pwsh -File tools/Export-Allocations.ps1 -Mode bayes
pwsh -File tools/Export-Allocations.ps1 -Mode equal
```

### CI smoke (dispatch workflow + download artifact)
```powershell
pwsh -File tools/Alloc-QA.ps1 -Mode ewma
```

### Report (compare latest vs previous timestamped file)
```powershell
pwsh -File tools/Alloc-Report.ps1
```

**Artifacts**: `artifacts/allocations/<ts>_alloc.csv`, `artifacts/allocations/latest.csv`

**CI workflow**: `.github/workflows/meta-alloc-smoke.yml` (dispatch-only; no push/PR triggers).

_Env in CI_: `AF_SKIP_MT5=1`, `PYTHONPATH=${{ github.workspace }}/src`
