Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot { (git rev-parse --show-toplevel) }
function Get-Branch    { (git rev-parse --abbrev-ref HEAD) }

$root = Get-RepoRoot
if (-not $root) { throw "Not inside a Git repo." }

$ai        = Join-Path $root 'ai_lab'
$statePath = Join-Path $ai   'state.json'
$manPath   = Join-Path $ai   'session_manifest.csv'
$auditOut  = Join-Path $ai   'audit_report.md'

$errors = @()

if (-not (Test-Path $statePath)) { $errors += 'state.json missing' }
else {
  $raw = Get-Content $statePath -Raw
  try { $state = $raw | ConvertFrom-Json -AsHashtable } catch { $errors += 'state.json invalid JSON' }
  if ($null -ne $state) {
    foreach ($k in 'project','repo_root','phase','active_feature','branch','commit','last_synced','owner') {
      if (-not $state.ContainsKey($k)) { $errors += "state.json missing key: $k" }
    }
    $branch = Get-Branch
    if ($state.branch -and $state.branch -ne $branch) { $errors += "HEAD branch '$branch' != state.branch '$($state.branch)'" }
    if ($state.commit) {
      $ok = (git rev-parse --verify "$($state.commit)^{commit}" 2>$null)
      if (-not $ok) { $errors += "state.commit not found: $($state.commit)" }
    }
  }
}

# If failing: write report + fail
if ($errors.Count) {
  ("# Audit Report`n`n" + ($errors | ForEach-Object { "- $_" } | Out-String)) | Set-Content -Encoding UTF8 $auditOut
  Write-Host "Audit: issues found -> $auditOut" -ForegroundColor Red
  exit 1
}

# SUCCESS: DO NOT write report unless explicitly requested
if ($env:AUDIT_WRITE_REPORT -eq '1') {
  "# Audit OK`n`nAll checks passed." | Set-Content -Encoding UTF8 $auditOut
  Write-Host "Audit: OK -> $auditOut"
} else {
  Write-Host "✅ Audit OK"
}
exit 0
