# Hooks Overview (PS7) — Alpha Factory

This repo uses PowerShell 7 hooks with LF line endings and a non-mutating push policy.

## Pre-commit (writers + linters)

Order (simplified):
1. black (system) — formatting (Python)
2. ruff (system) — linting (Python)
3. end-of-file-fixer / trailing-whitespace — hygiene
4. update-manifest — repo manifest refresh
5. Update-StateHash.ps1 — writer for i_lab/state.json (hash refresh) 
   - Runs at **commit time** so the state file is stable before push.

Tip: If you commit outside pre-commit (rare), run manually:
    pwsh -File tools/Update-StateHash.ps1
    git add ai_lab/state.json
    git commit -m "ci: refresh state hash"

## Pre-push (verify-only)

Executed on git push:
- Verify-Manifest — checks manifest is consistent
- Hook-PrePush-Handoff.ps1 — verify-only for state.json hash (no writes)
- Audit-State.ps1 — repo state sanity
- Hook-PrePush-Risk.ps1 — risk suite guard
- Handoff-Validate (no-write) — handoff invariants

If state.json is stale at push-time you’ll see:
  ❌ state.json hash was stale at push-time.
  Run: pwsh -File tools/Update-StateHash.ps1 ; git add ai_lab/state.json ; git commit -m 'ci: refresh state hash' ; git push

## Line endings

.gitattributes enforces **LF** for ps1/psm1/yml/yaml/md. CRLF→LF warnings on Windows are expected and safe.

## ChatOps quick commands

Pointers:
    "HEAD:   dcb0ea9"; "REMOTE: dcb0ea9"
    System.Management.Automation.OrderedHashtable = Get-Content ai_lab/state.json -Raw | ConvertFrom-Json
    "state.commit: 7807e2d"; "feature: chatops-20251021_230142"
    "session: 10/27/2025 14:47:05 / open"

Dispatch CI on main:
    gh workflow run ci.yml --ref main
    gh run list --workflow ci.yml --branch main -L 1 --json databaseId,status,conclusion,headSha

## Recovery recipes

Push blocked (file modified by hook):
    pwsh -File tools/Update-StateHash.ps1
    git add ai_lab/state.json
    git commit -m "ci: refresh state hash"
    git push

Advance state pointer to HEAD:
    ai_lab/state.json="ai_lab/state.json"; 7807e2d=(git rev-parse --short=7 HEAD).Trim()
    System.Management.Automation.OrderedHashtable=Get-Content ai_lab/state.json -Raw | ConvertFrom-Json -AsHashtable
    System.Management.Automation.OrderedHashtable['commit']=7807e2d; System.Management.Automation.OrderedHashtable['last_synced']=(Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    System.Management.Automation.OrderedHashtable | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 ai_lab/state.json
    git add ai_lab/state.json; git commit -m "ai_lab(state): advance commit pointer to HEAD 7807e2d"
