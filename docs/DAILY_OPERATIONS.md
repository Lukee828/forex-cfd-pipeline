# 🧭 Alpha Factory — Daily Operations (PowerShell 7)

Authoritative PS7 commands for Meta Allocator, Risk Suite, and daily reporting.
Assume PowerShell 7 and repo root as CWD. UTF-8 + LF.

---

## 🔹 Meta Allocator

Runs the allocator and writes a CSV like: artifacts/allocations/YYYYMMDD_HHMMSS_alloc.csv
```powershell
pwsh -File tools/Run-MetaAllocator.ps1
```

---

## 🔹 Daily Risk Report (with allocator section)

Builds artifacts/reports/latest.md, auto-appends allocator section, shows tail.
```powershell
pwsh -File tools/Make-DailyReport.ps1 -OutPath "artifacts/reports/latest.md"
```

---

## 🔹 Risk Report (base only)

Generate a minimal base report without re-running allocator.
```powershell
pwsh -File tools/Risk-Report.ps1 -OutPath "artifacts/reports/latest.md"
```

Append allocator to an existing report:
```powershell
pwsh -File tools/Post-Report-Include-Alloc.ps1 -ReportPath "artifacts/reports/latest.md"
```

---

## 🔹 Local Tests (quick)

Set import path for src/:
```powershell
$env:PYTHONPATH = "$PWD\src"
```

Contract tests:
```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/alpha_factory/test_meta_allocator_contract.py -vv
.\.venv311\Scripts\python.exe -m pytest -q tests/alpha_factory/test_registry.py -vv
```

Mini-suite:
```powershell
.\.venv311\Scripts\python.exe -m pytest -q --maxfail=1
```

---

## 🔹 CI Meta: Manual Dispatch (GitHub CLI)

Trigger:
```powershell
gh workflow run .github/workflows/ci-meta.yml --ref main
```

Watch latest:
```powershell
gh run list --workflow ci-meta.yml --branch main -L 1 --json databaseId,status,conclusion,headSha
```

---

## 🔹 Release Tag (example)
```powershell
pwsh -File tools/Release-Latest.ps1 -Tag "v1.0.3-meta-allocator" -Notes "Meta Allocator integrated; Risk Report includes allocator; Registry factors validated."
```

## Notes
- PowerShell 7 only.
- .gitattributes enforces LF for scripts/yaml.
- Run from repo root for relative paths.
