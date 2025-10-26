param(
  [string]$Feature = "",
  [switch]$WithLogs,
  [int]$Logs = 5,
  [switch]$Minimal,
  [switch]$Strict,
  [string]$ToFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot { git rev-parse --show-toplevel 2>$null }
function Get-Branch    { git rev-parse --abbrev-ref HEAD 2>$null }
function Get-Commit    { git rev-parse --short HEAD 2>$null }

$root = Get-RepoRoot
if (-not $root) { $root = (Get-Location).Path }

$aiDir   = Join-Path $root 'ai_lab'
$stateJs = Join-Path $aiDir 'state.json'
$lockJs  = Join-Path $aiDir 'lock.json'
$manCsv  = Join-Path $aiDir 'session_manifest.csv'

# --- Read state.json (tolerant)
$state = @{}
if (Test-Path $stateJs) {
  try { $state = (Get-Content $stateJs -Raw | ConvertFrom-Json -AsHashtable) } catch { $state = @{} }
}
$project        = $state.project        ?? ''
$repo_root      = $state.repo_root      ?? $root
$phase          = $state.phase          ?? ''
$state_feature  = $state.active_feature ?? ''
$state_branch   = $state.branch         ?? ''
$state_commit   = $state.commit         ?? ''
$owner          = $state.owner          ?? ''
$ai_guard       = $state.ai_guard       ?? ''
$last_synced    = $state.last_synced    ?? ''

$featureEff = if ($Feature) { $Feature } elseif ($state_feature) { $state_feature } else { '' }

# --- Read lock.json
$locked_by = ''
$locked_at = ''
if (Test-Path $lockJs) {
  try {
    $lock = Get-Content $lockJs -Raw | ConvertFrom-Json -AsHashtable
    $locked_by = $lock.locked_by ?? ''
    $locked_at = $lock.locked_at ?? ''
  } catch {}
}

# --- Read session_manifest.csv
$latestRow = $null
$recentRows = @()
if (Test-Path $manCsv) {
  $lines = Get-Content $manCsv
  if ($lines.Count -ge 2) {
    $rows = $lines[1..($lines.Count-1)]
    function Split-CsvLine([string]$line) {
      [regex]::Split($line, ',(?=(?:[^"]*"[^"]*")*[^"]*$)')
    }
    $cols = Split-CsvLine $rows[-1]
    if ($cols.Count -ge 9) {
      $latestRow = [ordered]@{
        timestamp = $cols[0]; branch=$cols[1]; feature=$cols[2]; commit=$cols[3]
        ai_guard=$cols[4]; pytest=$cols[5]; status=$cols[6]; summary=$cols[7].Trim('"'); log_path=$cols[8]
      }
    }
    if ($WithLogs) {
      $take = [Math]::Min($Logs, $rows.Count)
      for ($i=1; $i -le $take; $i++) {
        $colsN = Split-CsvLine $rows[-1*$i]
        if ($colsN.Count -ge 9) {
          $recentRows += ,([ordered]@{
            timestamp = $colsN[0]; branch=$colsN[1]; feature=$colsN[2]; commit=$colsN[3]
            ai_guard=$colsN[4]; pytest=$colsN[5]; status=$colsN[6]; summary=$colsN[7].Trim('"'); log_path=$colsN[8]
          })
        }
      }
    }
  }
}

# --- Live git info
$headBranch = Get-Branch
$headCommit = Get-Commit
$nowUtc     = (Get-Date).ToUniversalTime().ToString('s') + 'Z'

# --- Warnings
$warnings = @()
if ($state_branch -and $headBranch -and ($state_branch -ne $headBranch)) {
  $warnings += "HEAD branch '$headBranch' != state.branch '$state_branch'"
}
if ($state_commit -and $headCommit -and ($state_commit -ne $headCommit)) {
  $warnings += "HEAD commit '$headCommit' != state.commit '$state_commit'"
}
if ($locked_by) {
  $warnings += "lock active: locked_by=$locked_by locked_at=$locked_at"
}

# --- Compose handoff block
$lines = @()
$lines += '# handoff:v2'
$lines += "repo: $repo_root"
$lines += 'state: ai_lab/state.json'
$lines += "branch: $headBranch"
$lines += "commit: $headCommit"

if (-not $Minimal) {
  if ($project)    { $lines += "project: $project" }
  if ($phase)      { $lines += "phase: $phase" }
  if ($featureEff) { $lines += "feature: $featureEff" }
  if ($owner)      { $lines += "owner: $owner" }
  if ($ai_guard)   { $lines += "ai_guard: $ai_guard" }
  if ($last_synced){ $lines += "last_synced: $last_synced" }
  if ($locked_by)  { $lines += "locked_by: $locked_by" }
  if ($locked_at)  { $lines += "locked_at: $locked_at" }
  if ($latestRow) {
    $lines += 'latest_session:'
    $lines += "  utc: $($latestRow.timestamp)"
    $lines += "  status: $($latestRow.status)"
    $lines += "  pytest: $($latestRow.pytest)"
    $lines += "  ai_guard: $($latestRow.ai_guard)"
    if ($latestRow.summary) { $lines += "  summary: $($latestRow.summary)" }
    if ($latestRow.log_path){ $lines += "  log: $($latestRow.log_path)" }
  }
}

$lines += "generated_at: $nowUtc"
$lines += 'ask: continue from state.json; do not rely on prior chat memory.'

if ($warnings.Count -gt 0 -and -not $Minimal) {
  $lines += 'warnings:'
  foreach ($w in $warnings) { $lines += "  - $w" }
}

$block = ($lines -join "`n")

# --- Optional recent sessions tail
$tail = ''
if ($WithLogs -and $recentRows.Count -gt 0) {
  $tailLines = @()
  $tailLines += ''
  $tailLines += '# recent_sessions (latest first)'
  foreach ($r in $recentRows) {
    $tailLines += "- utc: $($r.timestamp)"
    $tailLines += "  branch: $($r.branch)"
    $tailLines += "  feature: $($r.feature)"
    $tailLines += "  commit: $($r.commit)"
    $tailLines += "  status: $($r.status)"
    $tailLines += "  pytest: $($r.pytest)"
    $tailLines += "  ai_guard: $($r.ai_guard)"
    if ($r.summary)  { $tailLines += "  summary: $($r.summary)" }
    if ($r.log_path) { $tailLines += "  log: $($r.log_path)" }
  }
  $tail = ($tailLines -join "`n")
}

# --- Print to console
Write-Host "`n=== COPY BELOW INTO NEW CHAT ===`n" -ForegroundColor Cyan
Write-Host $block -ForegroundColor Green
if ($tail) { Write-Host $tail -ForegroundColor DarkGray }
Write-Host "`n=== END COPY ===`n" -ForegroundColor Cyan

# --- Optional: write to file (markdown-friendly)  **FIXED QUOTING**
if ($ToFile) {
  $outPath = $ToFile
  if (-not ([System.IO.Path]::IsPathRooted($outPath))) {
    $outPath = Join-Path $root $outPath
  }
  $outDir = Split-Path $outPath -Parent
  if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

  $md = @()
  $md += '```yaml'
  $md += $block
  $md += '```'
  if ($tail) {
    $md += ''
    $md += '```yaml'
    $md += $tail
    $md += '```'
  }
  ($md -join "`n") | Set-Content -Encoding UTF8 $outPath
  Write-Host "Wrote handoff -> $outPath" -ForegroundColor Yellow
}

# --- Strict mode: non-zero exit on warnings
if ($Strict -and $warnings.Count -gt 0) {
  Write-Host 'Strict: warnings present; exiting 1' -ForegroundColor Red
  exit 1
}
exit 0
