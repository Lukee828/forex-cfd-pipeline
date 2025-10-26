# tools/Sync-ChatState.ps1
[CmdletBinding()]
param(
  [string]$Feature,
  [ValidateSet('pass','fail','unknown')] [string]$AiGuard,
  [string]$Owner,
  [string]$Notes,
  [switch]$Lock,
  [switch]$Unlock,
  # Optional explicit commit to record; defaults to current HEAD (short)
  [string]$Commit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-GitRoot      { (git rev-parse --show-toplevel).Trim() }
function Get-GitBranch    { (git rev-parse --abbrev-ref HEAD).Trim() }
function Get-GitShortSha  { (git rev-parse --short HEAD).Trim() }
function Sha1-String([string]$s) {
  $sha1  = [System.Security.Cryptography.SHA1]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
  ($sha1.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
}

$root = Get-GitRoot
if (-not $root) { throw "Not inside a Git repo." }

$ai        = Join-Path $root 'ai_lab'
$statePath = Join-Path $ai   'state.json'
$lockPath  = Join-Path $ai   'lock.json'
$prevPath  = Join-Path $ai   'state.prev'

# --------------------
# LOCK / UNLOCK
# --------------------
if ($Lock) {
  $by = ($Owner ? $Owner : $env:USERNAME)
  $lockObj = [ordered]@{
    branch    = Get-GitBranch
    locked_by = $by
    locked_at = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
  } | ConvertTo-Json -Compress
  $lockObj | Set-Content -Encoding UTF8 $lockPath
  Write-Host "🔒 Locked by $by on branch $(Get-GitBranch)" -ForegroundColor Yellow
  exit 0
}

if ($Unlock) {
  $lockObj = [ordered]@{
    branch    = Get-GitBranch
    locked_by = ''
    locked_at = ''
  } | ConvertTo-Json -Compress
  $lockObj | Set-Content -Encoding UTF8 $lockPath
  Write-Host "🔓 Lock released" -ForegroundColor Yellow
  exit 0
}

if (-not (Test-Path $statePath)) {
  throw "ai_lab/state.json not found — run tools/Init-ChatOps.ps1 first."
}

# --------------------
# LOAD + SNAPSHOT OLD
# --------------------
$oldJson = Get-Content $statePath -Raw
$oldHash = Sha1-String $oldJson
$state   = Get-Content $statePath -Raw | ConvertFrom-Json -AsHashtable

# --------------------
# APPLY UPDATES
# --------------------
if ($Feature) { $state.active_feature = $Feature }
if ($Owner)   { $state.owner          = $Owner }
if ($AiGuard) { $state.ai_guard       = $AiGuard }
if ($Notes)   { $state.notes          = $Notes }

$commitEff         = if ($Commit) { $Commit.Trim() } else { Get-GitShortSha }
$state.branch      = Get-GitBranch
$state.commit      = $commitEff
$state.last_synced = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
$state.prev_hash   = $oldHash

# --------------------
# RECOMPUTE HASH (blank hash field first)
# --------------------
$copy = [ordered]@{}
foreach ($k in $state.Keys) { $copy[$k] = $state[$k] }
$copy['hash'] = ''

$jsonTmp    = ($copy | ConvertTo-Json -Depth 32)
$state.hash = Sha1-String $jsonTmp

# --------------------
# WRITE OUT (UTF8 + newline)
# --------------------
$oldHash | Set-Content -Encoding UTF8 $prevPath
($state | ConvertTo-Json -Depth 32) | Set-Content -Encoding UTF8 $statePath

Write-Host ("✔ Synced state.json → {0}@{1}" -f $state.branch, $state.commit) -ForegroundColor Green
