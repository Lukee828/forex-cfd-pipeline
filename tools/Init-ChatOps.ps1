param(
  [string]$Owner = $env:USERNAME,
  [string]$Project = 'Alpha Factory',
  [string]$Feature = 'risk_governor'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $repoRoot) { throw 'Not inside a Git repo.' }
$ai = Join-Path $repoRoot 'ai_lab'
$null = New-Item -ItemType Directory -Path (Join-Path $ai 'session_logs') -Force
$null = New-Item -ItemType Directory -Path (Join-Path $ai 'assistants') -Force
$null = New-Item -ItemType Directory -Path (Join-Path $ai 'plan') -Force
$null = New-Item -ItemType Directory -Path (Join-Path $ai 'snapshots') -Force
$statePath = Join-Path $ai 'state.json'
$lockPath  = Join-Path $ai 'lock.json'
$manPath   = Join-Path $ai 'session_manifest.csv'
$hbPath    = Join-Path $ai 'heartbeat.log'
$prevPath  = Join-Path $ai 'state.prev'
if (-not (Test-Path $statePath)) {
  $initial = [ordered]@{
    project       = $Project
    repo_root     = $repoRoot
    phase         = 'v1.0-infra'
    active_feature= $Feature
    branch        = (git rev-parse --abbrev-ref HEAD)
    commit        = (git rev-parse --short HEAD)
    last_synced   = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
    owner         = $Owner
    ai_guard      = 'unknown'
    notes         = ''
    hash          = ''
    prev_hash     = ''
  } | ConvertTo-Json -Depth 6
  $initial | Set-Content -Encoding UTF8 $statePath
  '' | Set-Content -Encoding UTF8 $prevPath
}
if (-not (Test-Path $lockPath)) { '{"branch":"","locked_by":"","locked_at":""}' | Set-Content -Encoding UTF8 $lockPath }
if (-not (Test-Path $manPath)) { 'timestamp,branch,feature,commit,ai_guard,pytest,status,summary,log_path' | Set-Content -Encoding UTF8 $manPath }
if (-not (Test-Path $hbPath))  { '' | Set-Content -Encoding UTF8 $hbPath }
Write-Host '✅ Chat-Ops bootstrap complete.' -ForegroundColor Green
