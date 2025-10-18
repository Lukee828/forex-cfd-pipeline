param()
#requires -Version 7.0
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$fail = $false

function Write-OK    ($m){ Write-Host "OK  $m" -ForegroundColor Green }
function Write-WARN  ($m){ Write-Host "WARN $m" -ForegroundColor Yellow }
function Write-FAIL  ($m){ Write-Host "FAIL $m" -ForegroundColor Red }

# Derive owner/repo from origin
$remote = (git remote get-url origin).Trim()
if (-not ($remote -match '[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(?:\.git)?$')) {
  Write-FAIL "Cannot parse origin remote: $remote"; exit 1
}
$owner = $Matches.owner; $repo = $Matches.repo

Write-Host "=== Repo Health ===" -ForegroundColor Cyan

# 1) Branch protection: contexts must include lint, test, guard
$prot = gh api "repos/$owner/$repo/branches/main/protection" -q `
  '{contexts:.required_status_checks.contexts, strict:.required_status_checks.strict}' 2>$null
if (-not $prot) { Write-FAIL "Could not fetch branch protection"; exit 1 }
$contexts = ($prot | ConvertFrom-Json).contexts
$need = @("lint","test","Check for push or pull_request_target triggers")
$missing = $need | Where-Object { $_ -notin $contexts }
if ($missing) { Write-FAIL ("Missing required check(s): " + ($missing -join ", ")); $fail = $true }
else { Write-OK ("Required checks present: " + ($contexts -join ", ")) }

# 2) Workflows must NOT have on: push or pull_request_target
$wfRoot = ".github/workflows"
if (-not (Test-Path $wfRoot)) { Write-FAIL "No $wfRoot directory"; $fail = $true }
else {
  $bad = @()
  $files = Get-ChildItem $wfRoot -File -Recurse -Include *.yml,*.yaml
  foreach ($f in $files) {
    $txt = Get-Content -Raw $f.FullName
    if ($txt -match '(?m)^\s*push\s*:') { $bad += "$($f.Name): push" }
    if ($txt -match '(?m)^\s*pull_request_target\s*:') { $bad += "$($f.Name): pull_request_target" }
  }
  if ($bad) { Write-FAIL ("Forbidden triggers: " + ($bad -join "; ")); $fail = $true }
  else { Write-OK "No forbidden triggers in workflow files" }
}

# 3) Guard workflow recent status (optional, informative)
$guard = gh run list --workflow "Check for push or pull_request_target triggers" --limit 1 `
  --json headBranch,event,status,conclusion -q '.[0]' 2>$null
if ($guard) { Write-OK ("Guard last run: " + $guard) } else { Write-WARN "No guard runs found yet" }

# 4) Last 10 runs on main must not include push
$runs = gh run list --branch main --limit 10 --json event -q '[].event' 2>$null
if ($runs) {
  $events = $runs | ConvertFrom-Json
  if ($events -contains "push") { Write-FAIL "Recent runs on main include 'push'"; $fail = $true }
  else { Write-OK "No 'push' runs on main in last 10" }
} else {
  Write-WARN "Could not read recent runs on main"
}

# 5) Local pre-push guard hook present (warn-only)
$hasHook = (Test-Path ".git/hooks/pre-push") -or (Test-Path ".git/hooks/pre-push.ps1")
if ($hasHook) { Write-OK "Local pre-push guard present" } else { Write-WARN "Local pre-push guard missing" }

if ($fail) { exit 1 } else { Write-Host "`n✅ Repo health OK" -ForegroundColor Green; exit 0 }

# Recent runs on main (robust)
try {
  $recent = gh run list --branch main --limit 5 --json databaseId,workflowName,event,status,conclusion 2>$null | ConvertFrom-Json
  if ($recent -and $recent.Count -gt 0) {
    "OK  Recent runs on main:"
    $recent | ForEach-Object { "   $($_.workflowName) — $($_.event) — $($_.status)/$($_.conclusion)" }
  } else {
    "OK  No recent runs on main (or none returned)"
  }
} catch {
  "OK  No recent runs on main (or none returned)"
}
# End recent runs

