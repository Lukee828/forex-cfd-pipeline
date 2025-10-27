# 🧩 Pre-Commit / Pre-Push Automation Overview

Generated automatically from **.pre-commit-config.yaml**.

| Stage | Purpose | Hooks | Runs |
|-------|----------|--------|------|
| **pre-commit** | Formatting + linting + writers. | $((black-local -join ', ')) | On every git commit |
| **pre-push** | Validation / audit / risk guards. | $(( -join ', ')) | On every git push |

---

## 🔁 Flow Summary
Commit → format / lint / fixers / manifest / state-hash  
Push → verify manifest / audit / handoff / risk governor

---

## 📂 Hook Script Locations
All hooks live under 	ools/ and are PowerShell 7 only.

---

_Last regenerated: 2025-10-27 14:59:04 (UTC+1 Warsaw)_
