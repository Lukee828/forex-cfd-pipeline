param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
[CmdletBinding()]
param(
  [string]$Pairs = "EURUSD,GBPUSD",
  [string]$TF    = "H1",
  [string]$Start = "2024-01-01",
  [string]$End   = "2024-01-10",
  [switch]$Dispatch
)

function Write-Note($msg) { Write-Host $msg -ForegroundColor Cyan }

if ($Dispatch) {
  Write-Note "Dispatching 'Manual Export' with inputs: pairs=$Pairs tf=$TF $Start..$End"
  gh workflow run "Manual Export" `
    -f pairs="$Pairs" `
    -f tf="$TF" `
    -f start="$Start" `
    -f end="$End" `
    -f upload_to_s3=false | Out-Null
}

Write-Note "Locating latest run id for manual-export.yml..."
$runId = $null
1..60 | ForEach-Object {
  $runId = gh run list --workflow manual-export.yml --limit 1 `
            --json databaseId,status,headBranch,event `
            --jq '.[0].databaseId' 2>$null
  if ($runId) { break }
  Start-Sleep -Seconds 2
}
if (-not $runId) { throw "No recent run found for manual-export.yml" }
Write-Note "Found run id: $runId"

$target = Join-Path "artifacts_download" "feature-exports-$runId"
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Force -Path $target | Out-Null

Write-Note "Downloading artifact 'feature-exports-$runId' to $target"
$downloaded = $true
try {
  gh run download $runId --name "feature-exports-$runId" --dir $target 2>$null
} catch {
  $downloaded = $false
}
if (-not $downloaded) {
  gh run download $runId --dir $target
}

Write-Note "Contents:"
Get-ChildItem -Recurse $target | Select-Object FullName, Length

$csv = Join-Path $target "exports\fallback.csv"
if (Test-Path $csv) {
  Write-Note "CSV path: $csv"
  Import-Csv $csv | Format-Table
} else {
  Write-Note "No fallback.csv found. Listing artifacts in the run:"
  gh api "repos/:owner/:repo/actions/runs/$runId/artifacts" `
    --jq '.artifacts[] | {name,id,size_in_bytes}'
}
