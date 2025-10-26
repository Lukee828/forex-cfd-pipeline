param(
  [string]$Feature,
  [ValidateSet("pass","fail","unknown")][string]$AiGuard,
  [string]$Owner,
  [string]$Notes,
  [switch]$Lock,
  [switch]$Unlock
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot { (git rev-parse --show-toplevel) }
function Get-Branch    { (git rev-parse --abbrev-ref HEAD) }
function Get-ShortCommit { (git rev-parse --short HEAD) }
function Get-StringHash([string]$s) {
  $sha1  = [System.Security.Cryptography.SHA1]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
  ($sha1.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
}

$root = Get-RepoRoot
if (-not $root) { throw "Not inside a Git repo." }
$ai        = Join-Path $root 'ai_lab'
$statePath = Join-Path $ai   'state.json'
$lockPath  = Join-Path $ai   'lock.json'
$prevPath  = Join-Path $ai   'state.prev'

# --- LOCK / UNLOCK (use $lockObj to avoid colliding with [switch]$Lock) ---
if ($Lock) {
  $lockObj = @{
    branch    = (Get-Branch)
    locked_by = ($Owner ? $Owner : $env:USERNAME)
    locked_at = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
  } | ConvertTo-Json -Compress
  $lockObj | Set-Content -Encoding UTF8 $lockPath
  Write-Host "🔒 Locked by $($Owner ? $Owner : $env:USERNAME) on branch $(Get-Branch)" -ForegroundColor Yellow
  exit 0
}
if ($Unlock) {
  $lockObj = @{
    branch    = (Get-Branch)
    locked_by = ''
    locked_at = ''
  } | ConvertTo-Json -Compress
  $lockObj | Set-Content -Encoding UTF8 $lockPath
  Write-Host "🔓 Lock released" -ForegroundColor Yellow
  exit 0
}

if (-not (Test-Path $statePath)) { throw "ai_lab/state.json not found — run tools/Init-ChatOps.ps1 first." }

# --- Load, update, hash ---
$state   = Get-Content $statePath -Raw | ConvertFrom-Json -AsHashtable
$oldJson = Get-Content $statePath -Raw
$oldHash = Get-StringHash $oldJson

if ($Feature) { $state.active_feature = $Feature }
if ($Owner)   { $state.owner          = $Owner }
if ($AiGuard) { $state.ai_guard       = $AiGuard }
if ($Notes)   { $state.notes          = $Notes }

$state.branch      = Get-Branch
$state.commit      = Get-ShortCommit
$state.last_synced = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
$state.prev_hash   = $oldHash

# compute new hash with hash field blanked
$copy        = $state.Clone()
$copy['hash']= ''
$jsonTmp     = ($copy | ConvertTo-Json -Depth 10)
$state.hash  = Get-StringHash $jsonTmp

$oldHash | Set-Content -Encoding UTF8 $prevPath
($state | ConvertTo-Json -Depth 10) | Set-Content -Encoding UTF8 $statePath
Write-Host "✔ Synced state.json → $($state.branch)@$($state.commit)" -ForegroundColor Green
