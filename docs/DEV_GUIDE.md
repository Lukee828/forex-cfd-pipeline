# Pointers
"HEAD: $(git rev-parse --short=7 HEAD)"; "REMOTE: $(git rev-parse --short=7 origin/main)"
$s=Get-Content ai_lab/state.json -Raw | ConvertFrom-Json
"state.commit: $($s.commit)"; "feature: $($s.feature)"
"session: $($s.latest_session.utc) / $($s.latest_session.status)"

# Stabilize & push
pwsh -File tools/Update-StateHash.ps1
git add ai_lab/state.json
git commit -m "ci: refresh state hash"
git push

# CI dispatch & watch
gh workflow run ci.yml --ref main
$run = gh run list --workflow ci.yml --branch main -L 1 --json databaseId,status,conclusion,headSha | ConvertFrom-Json
$run

# Developer Guide — Alpha Factory (PS7)

> Windows + PowerShell 7 only. Repo uses PR-only workflow, LF line endings, and pre-commit hooks.

## 0) Pointers & Status (daily warm-up)

```powershell
Set-Location "C:\Users\speed\Desktop\forex-standalone"
"HEAD:   $(git rev-parse --short=7 HEAD)"; "REMOTE: $(git rev-parse --short=7 origin/main)"
$st = Get-Content ai_lab/state.json -Raw | ConvertFrom-Json
"state.commit: $($st.commit)"; "branch: $($st.branch)"; "feature: $($st.feature)"
"session: $($st.latest_session.utc) / $($st.latest_session.status)"
Test-Path $st.latest_session.log
## Daily Ops (quick)

### 1) Morning warm-up

```powershell
Set-Location C:\Users\speed\Desktop\forex-standalone
"HEAD: $(git rev-parse --short=7 HEAD)"; "REMOTE: $(git rev-parse --short=7 origin/main)"
$st = Get-Content ai_lab/state.json -Raw | ConvertFrom-Json
"state.commit: $($st.commit)"; "branch: $($st.branch)"; "feature: $($st.feature)"
"session: $($st.latest_session.utc) / $($st.latest_session.status)"
Test-Path $st.latest_session.log
```

### 2) Work loop (edit -> commit)

```powershell
pre-commit run -a
pwsh -File tools/Update-StateHash.ps1
git add -A
git commit -m "feat: describe change"
```

### 3) Push (verify-only hooks run)

```powershell
git push origin main
```

### 4) CI dispatch & watch (main)

```powershell
gh workflow run ci.yml --ref main
gh run list --workflow ci.yml --branch main -L 1 --json databaseId,status,conclusion,headSha
```

### 5) End-of-day wrap (close session)

```powershell
$sp = "ai_lab/state.json"
$sha = (git rev-parse --short=7 HEAD).Trim()
$h = Get-Content $sp -Raw | ConvertFrom-Json -AsHashtable
$h["commit"]      = $sha
$h["last_synced"] = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$ls = $h["latest_session"]
if (-not $ls.ContainsKey("end_utc")) { $ls["end_utc"] = $null }
$ls["end_utc"] = (Get-Date).ToUniversalTime().ToString("s") + "Z"
$ls["status"]  = "closed"
$h | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $sp
git add $sp
git commit -m "ai_lab(session): close day; advance pointer to HEAD $sha"
pwsh -File tools/Update-StateHash.ps1
git add ai_lab/state.json
git commit -m "ci: refresh state hash"
git push origin main
```

Notes:
- Update-StateHash.ps1 runs at pre-commit; pre-push is verify-only (no writes).
- CRLF to LF warnings are expected due to .gitattributes.
