# Forex CFD Pipeline

> Lean, testable research sandbox with an **Alpha Factory** and guardrails.

## Quickstart
```pwsh
python -m venv .venv
.\.venv\Scripts\pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python .\tools\Smoke-AlphaFactory.py
.\.venv\Scripts\python .\examples\run_alpha_factory.py
.\.venv\Scripts\python -m pytest -q
```
## Badges

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
### FeatureStore demo

Run:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-FeatureStoreDemo.ps1 -Symbol EURUSD -Rows 10
```

Ping: 2025-10-10T09:48:30.8212332+02:00

### Headless Matplotlib in CI
We run Matplotlib in headless mode to avoid GUI backends (e.g., Tk).
The PowerShell 7 script below verifies an Agg backend is available in CI:

```pwsh
./tools/ensure-agg.ps1
```

This script:
- Confirms Python + Matplotlib import;
- Prints current backend and verifies Agg import path;
- Exits non-zero on failure (CI fails fast).

Executed automatically in GitHub Actions before `pytest`.
