Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot { (git rev-parse --show-toplevel) }
function Get-StringHash([string]$s) {
  $sha1  = [System.Security.Cryptography.SHA1]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
  ($sha1.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
}

$root = Get-RepoRoot
if (-not $root) { throw "Not inside a Git repo." }
$statePath = Join-Path $root 'ai_lab/state.json'
if (-not (Test-Path $statePath)) { throw "ai_lab/state.json not found — run tools/Init-ChatOps.ps1 first." }

# Load current state
$state = Get-Content $statePath -Raw | ConvertFrom-Json -AsHashtable

# Compute expected hash WITHOUT mutating dynamic fields
$copy = $state.Clone()
$copy['hash'] = ''   # blank the hash field only
$jsonTmp = ($copy | ConvertTo-Json -Depth 12)
$newHash = Get-StringHash $jsonTmp

if ($state.hash -ne $newHash) {
  $state.hash = $newHash
  ($state | ConvertTo-Json -Depth 12) | Set-Content -Encoding UTF8 $statePath
  Write-Host "✔ state.json hash updated" -ForegroundColor Green
} else {
  Write-Host "✓ state.json hash already up-to-date" -ForegroundColor DarkGreen
}
