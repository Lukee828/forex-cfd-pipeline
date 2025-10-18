[![CI](https://github.com/Lukee828/forex-cfd-pipeline/actions/workflows/ci.yml/badge.svg?branch=chore/compat-alpha-factory-027)](https://github.com/Lukee828/forex-cfd-pipeline/actions/workflows/ci.yml)

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

