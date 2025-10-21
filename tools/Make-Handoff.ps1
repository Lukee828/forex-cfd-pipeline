param([string]$Feature = "")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot { git rev-parse --show-toplevel }
$root   = Get-RepoRoot
$branch = (git rev-parse --abbrev-ref HEAD 2>$null)
$commit = (git rev-parse --short HEAD 2>$null)
$state  = "ai_lab/state.json"

if (-not $root) { $root = (Get-Location).Path }

$featureLine = if ($Feature) { "feature: $Feature" } else { "feature: <next_module>" }

$block = @"
# handoff:v2
repo: $root
state: $state
branch: $branch
commit: $commit
$featureLine
ask: continue from state.json; do not rely on prior chat memory.
"@

Write-Host "`n=== COPY BELOW INTO NEW CHAT ===`n" -ForegroundColor Cyan
Write-Host $block -ForegroundColor Green
Write-Host "=== END COPY ===`n" -ForegroundColor Cyan
