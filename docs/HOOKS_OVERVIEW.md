# 🧩 Pre-Commit / Pre-Push Automation Overview

This repo uses pre-commit for two stages:

| Stage | Purpose | Hooks | When |
|---|---|---|---|
| **pre-commit** | Formatting, linting, and writers. | `black-local`, `ruff-local`, `end-of-file-fixer`, `trailing-whitespace`, `update-manifest`, `update-state-hash` | On every `git commit` |
| **pre-push** | Validation/audit/risk guards (no writers). | `verify-manifest`, `audit-state`, `handoff-validate`, `risk-governor` | On every `git push` |

## 🔁 Flow Summary
Commit → format/lint/fixers + manifest + state-hash  
Push   → verify-manifest + audit + handoff + risk

## Handy commands
- Run commit-time hooks: `pre-commit run -a -v`
- Run push-time hooks: `pre-commit run --hook-stage pre-push -a -v`
- Reinstall hooks: `pre-commit clean; pre-commit install --hook-type pre-commit --hook-type pre-push --overwrite`

## Common issues
- **Here-strings**: terminator `'@` must be at column 1 **and alone** on its line.
- **Line endings**: `.gitattributes` enforces LF for scripts/yaml/markdown to avoid churn.
- **PowerShell policy**: call scripts via `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Script.ps1`.
