# tools/Session-Commit.ps1
[CmdletBinding()]
param(
  [string]$Feature,                                   # optional; inferred from branch if missing
  [string]$Summary,                                   # optional; default message if missing
  [ValidateSet('pass','fail','unknown')] [string]$AiGuard = 'unknown',
  [ValidateSet('pass','fail','na')]      [string]$Pytest  = 'na',
  [ValidateSet('draft','open','merged','abandoned')] [string]$Status = 'draft',
  [int]$PR,
  [string[]]$Touched   = @(),
  [string[]]$FollowUps = @(),
  [string]$Owner,
  [switch]$NoCommit                                     # set to skip git commit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Say($msg, $color='Cyan') { Write-Host $msg -ForegroundColor $color }

function Get-RepoRoot   { (git rev-parse --show-toplevel).Trim() }
function Get-Branch     { (git rev-parse --abbrev-ref HEAD).Trim() }
function Get-ShortSHA   { (git rev-parse --short HEAD).Trim() }

# --- repo context
$root   = Get-RepoRoot
$branch = Get-Branch
$commit = Get-ShortSHA

# --- infer Feature if not provided (take last path segment of branch; fall back to 'general')
if (-not $Feature -or -not $Feature.Trim()) {
  $Feature = ($branch -split '/')[-1]
  if ([string]::IsNullOrWhiteSpace($Feature)) { $Feature = 'general' }
}

# --- default Summary if not provided
if (-not $Summary -or -not $Summary.Trim()) {
  $Summary = "session update ($branch@$commit)"
}

# --- default Owner
if (-not $Owner -or -not $Owner.Trim()) { $Owner = $env:USERNAME }

# --- paths
$ai      = Join-Path $root 'ai_lab'
$logDir  = Join-Path $ai   'session_logs'
$manPath = Join-Path $ai   'session_manifest.csv'
$stateJs = Join-Path $ai   'state.json'
$null = New-Item -ItemType Directory -Path $logDir -Force

# --- generate log filename & front-matter
$utc     = (Get-Date).ToUniversalTime()
$utcIso  = $utc.ToString('s') + 'Z'
$slug    = ("{0}-{1}-{2}" -f $utcIso.Replace(':','-').Replace('T','_').Substring(0,19), $branch.Replace('/','-'), $Feature).ToLower()
$logPath = Join-Path $logDir ($slug + '.md')

$front = @(
  '---'
  "utc: $utcIso"
  "branch: $branch"
  "commit: $commit"
  "feature: $Feature"
  "summary: `"$Summary`""
  "ai_guard: $AiGuard"
  "pytest: $Pytest"
  "status: $Status"
  $(if ($PR) { "pr: $PR" } else { $null })
  '---'
) -join "`n"

# --- notes block
$notes = @('# Notes')
if ($Touched.Count)   { $notes += '- touched:';    $notes += ($Touched   | ForEach-Object { "  - $_" }) } else { $notes += '- touched: []' }
if ($FollowUps.Count) { $notes += '- follow-ups:'; $notes += ($FollowUps | ForEach-Object { "  - $_" }) } else { $notes += '- follow-ups: []' }

# --- write log
($front + "`n" + ($notes -join "`n") + "`n") | Set-Content -Encoding UTF8 $logPath
Say "✔ Wrote session log → $logPath" 'Green'

# --- append manifest (create header once)
if (-not (Test-Path $manPath)) {
  'timestamp,branch,feature,commit,ai_guard,pytest,status,summary,log_path' | Set-Content -Encoding UTF8 $manPath
}
$csvLine = ('{0},{1},{2},{3},{4},{5},{6},"{7}",{8}' -f
  $utcIso,$branch,$Feature,$commit,$AiGuard,$Pytest,$Status,$Summary,$logPath)
Add-Content -Path $manPath -Value ($csvLine + "`n") -Encoding UTF8
Say "✔ Updated manifest" 'Green'

# --- update state.json (prefer Sync-ChatState.ps1; fallback to direct edit)
try {
  $sync = Join-Path $root 'tools/Sync-ChatState.ps1'
  if (Test-Path $sync) {
    & pwsh -NoProfile -File $sync -Feature $Feature -AiGuard $AiGuard -Owner $Owner -Notes $Summary | Out-Null
    Say "✔ Synced state via Sync-ChatState.ps1" 'Green'
  } elseif (Test-Path $stateJs) {
    $state = Get-Content $stateJs -Raw | ConvertFrom-Json
    $state.feature = $Feature
    $state.branch  = $branch
    $state.commit  = $commit
    $state.owner   = $Owner
    $state.ai_guard = $AiGuard
    $state.latest_session = [ordered]@{
      utc     = $utcIso
      status  = $Status
      pytest  = $Pytest
      ai_guard= $AiGuard
      summary = $Summary
      log     = $logPath
    }
    ($state | ConvertTo-Json -Depth 12) | Set-Content -Encoding UTF8 $stateJs
    Say "✔ Updated state.json (fallback)" 'Green'
  } else {
    Say "state.json missing; skipped state update" 'Yellow'
  }
} catch {
  Say "Warning: state update failed → $_" 'Yellow'
}

# --- optionally commit artifacts
if (-not $NoCommit) {
  git add "ai_lab/session_logs" "ai_lab/session_manifest.csv" "ai_lab/state.json" 2>$null
  git commit -m $Summary | Out-Null
  Say "✔ Committed session artifacts" 'Green'
} else {
  Say "(NoCommit) Skipped git commit." 'Yellow'
}
