# Pre-Commit / Pre-Push Automation Overview

## Stages

| Stage | Purpose | Hooks | When |
|------|---------|-------|------|
| **pre-commit** | Formatting, linting, and manifest/state writers. | `black-local`, `ruff-local`, `end-of-file-fixer`, `trailing-whitespace`, `update-manifest`, `update-state-hash` | Before every `git commit` |
| **pre-push**   | Validation, audit, and risk guards.               | `verify-manifest`, `audit-state`, `handoff-validate`, `risk-governor` | Before every `git push` |

---

## Flow Summary
Commit → format / lint / fixers / manifest / state-hash
Push   → verify manifest / audit / handoff / risk governor

---

## Hook Script Locations
All hook scripts live under `tools/` and are PowerShell 7 only.

---
_Last regenerated: 2025-10-27 15:26:12 (Local)_