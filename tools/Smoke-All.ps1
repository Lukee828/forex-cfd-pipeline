# tools/Smoke-All.ps1
<#
Runs an end-to-end smoke of your ChatOps layer:
 - validates tools presence and repo cleanliness,
 - audits state,
 - exercises pre-commit (commit stage) and pre-push (push stage),
 - verifies Strict handoff gate blocks on drift and passes when fixed,
 - leaves your repo exactly where it started.
Safe to run repeatedly; creates/cleans a temporary branch.
#>

param(
  [int]$SinceHours = 36,
  [switch]$VerboseOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Pretty print helper
if (-not (Get-Command Say -ErrorAction SilentlyContinue)) {
  function Say {
    param([string]$Message, [string]$Color = 'Cyan')
    Write-Host $Message -ForegroundColor $Color
  }
}

# --- Locate repo root
$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) { throw "Not inside a git repository." }
Set-Location $root

# --- Must-have files
$must = @(
  'ai_lab/state.json',
  'tools/Audit-State.ps1',
  'tools/Hook-Audit.ps1',
  'tools/Hook-PrePush-Handoff.ps1',
  'tools/Make-Handoff.ps1',
  'tools/Sync-ChatState.ps1',
  'tools/Session-Commit.ps1',
  'tools/On-PostPush.ps1',
  '.pre-commit-config.yaml'
)
$missing = $must | Where-Object { -not (Test-Path $_) }
if ($missing) { throw "Missing files:`n - " + ($missing -join "`n - ") }

# --- Capture start point
$startBranch = (git rev-parse --abbrev-ref HEAD).Trim()
$startCommit = (git rev-parse --short HEAD).Trim()
Say "Start: $startBranch@$startCommit"

# Keep state to restore later
$prevLocation = Get-Location

# Always restore branch & location even on failure
$TempBranch = $null
try {
  # --- Pre-flight: validate pre-commit config
  pre-commit validate-config | Out-Host

  # --- Clean caches to avoid Windows lock weirdness
  $env:PRE_COMMIT_HOME = "$root/.precommit_cache"
  New-Item -ItemType Directory -Force -Path $env:PRE_COMMIT_HOME | Out-Null
  pre-commit clean | Out-Null

  # --- Read-only audit
  pwsh -NoProfile -File tools/Audit-State.ps1 | Out-Host

  # --- Analyze recent repo activity (if the analyzer exists)
  if (Test-Path 'tools/Analyze-RepoState.ps1') {
    pwsh -NoProfile -File tools/Analyze-RepoState.ps1 -SinceHours $SinceHours | Out-Host
  } else {
    Say "Analyze-RepoState.ps1 not present (skip)" "Yellow"
  }

  # --- Ensure hooks are installed (commit + push)
  pre-commit install --hook-type pre-commit --hook-type pre-push --overwrite | Out-Null

  # --- Commit-stage hooks sanity
  $global:LASTEXITCODE = 0
  pre-commit run --hook-stage commit -a -v | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Commit-stage pre-commit failed." }

  # --- Create a temp branch and simulate a full session
  $TempBranch = "smoke/chatops-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
  git switch -c $TempBranch | Out-Null

  # Session open/close to exercise logs/manifest
  pwsh -NoProfile -File tools/Session-Commit.ps1 -Feature risk_governor -Summary "smoke open" -Status open -AiGuard unknown -Pytest na | Out-Host
  pwsh -NoProfile -File tools/On-PostPush.ps1 -Status merged -Pytest na -AiGuard pass -Summary "smoke close" | Out-Host

  # --- Push-stage hooks should PASS cleanly
  $global:LASTEXITCODE = 0
  pre-commit run --hook-stage push -a -v | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Push-stage pre-commit failed (clean run)." }

  # --- NEGATIVE TEST: force a mismatch to ensure Strict gate blocks
  Say "Simulating drift: setting state.json.commit to PREVIOUS commit (should FAIL Strict gate)" "Yellow"
  $headShort = (git rev-parse --short HEAD).Trim()
  $prevFull  = (git rev-list --max-count=1 "$headShort~1" 2>$null)

  if ($prevFull) {
    # 1) Dirty-edit state.json (NO commit): create HEAD vs state mismatch
    $statePath = Join-Path $root 'ai_lab/state.json'
    $stateObj  = Get-Content $statePath -Raw | ConvertFrom-Json
    $stateObj.commit = $prevFull.Substring(0,7)
    ($stateObj | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $statePath

    # 2) Run push-stage hooks directly; expect non-zero exit
    pre-commit clean | Out-Null
    $global:LASTEXITCODE = 0
    pre-commit run --hook-stage push -a -v | Out-Host
    $failedOnDrift = ($LASTEXITCODE -ne 0)
    if (-not $failedOnDrift) {
      throw "Strict handoff did NOT fail on drift!"
    } else {
      Say "Strict handoff correctly failed on drift ✅" "Green"
    }

    # 3) Restore state.json back to HEAD (undo the dirty edit)
    git restore --source=HEAD -- ai_lab/state.json

    # 4) Prove push hooks now PASS when aligned
    $global:LASTEXITCODE = 0
    pre-commit run --hook-stage push -a -v | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "Push-stage hooks should pass after restoring state.json!"
    } else {
      Say "Push-stage hooks pass after restore ✅" "Green"
    }
  } else {
    Say "Could not compute previous commit; skipping negative test." "Yellow"
  }

  Say "✅ Smoke-All complete on $startBranch@$startCommit" "Green"
}
finally {
  # Always return to the original branch & cleanup temp branch
  try {
    if ($TempBranch) {
      Say "Smoke: restoring original branch $startBranch" "Cyan"
      git switch $startBranch 2>$null | Out-Null
      git branch -D $TempBranch 2>$null | Out-Null
    }
  } catch { }
  Set-Location $prevLocation
}
