# ⚙️ CI Meta Workflow — .github/workflows/ci-meta.yml

Lightweight CI to validate Meta Allocator + Registry + Risk Report integration.

---

## Triggers (allowed)
```yaml
on:
  pull_request:
  workflow_dispatch:
```
- NO push:
- NO pull_request_target:
- Manual dispatch allowed.

---

## Job Outline
```yaml
jobs:
  meta:
    name: Meta Allocator Smoke
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        shell: pwsh
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -c .github/constraints-ci.txt
          pip install pytest==8.4.2

      - name: Run contract tests
        shell: pwsh
        run: |
          $env:PYTHONPATH = "src"
          python -m pytest -q tests/alpha_factory/test_meta_allocator_contract.py -vv
          python -m pytest -q tests/alpha_factory/test_registry.py -vv

      - name: Build daily risk report
        shell: pwsh
        run: |
          pwsh -File tools/Make-DailyReport.ps1 -OutPath "artifacts/reports/latest.md"

      - name: Upload allocation CSVs
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: allocations
          path: artifacts/allocations/*.csv
          if-no-files-found: ignore

      - name: Upload report
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: risk-report
          path: artifacts/reports/latest.md
          if-no-files-found: error
```

---

## Manual Run (CLI)
```powershell
gh workflow run .github/workflows/ci-meta.yml --ref main
gh run list --workflow ci-meta.yml --branch main -L 1 --json databaseId,status,conclusion,headSha
gh run view <RUN_ID> --log-failed
```

---

## Outcome
- Confirms allocator stability, registry examples present, and PS7 report pipeline OK.
- Uploads current allocations CSV + latest daily report as artifacts.
