# tools/Release-Tag.ps1  (PS7-only)
[CmdletBinding()]
param(
  [Parameter(Position=0)] [string]$PR,
  [string]$Tag,
  [string]$Branch = 'main',
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

function Ensure-InRepo { try { (git rev-parse --show-toplevel) | Out-Null } catch { throw "Not inside a git repository." } }
function Resolve-PRNumber([string]$p){
  if ([string]::IsNullOrWhiteSpace($p)) { return $null }
  if ($p -match '/pull/(\d+)') { return [int]$Matches[1] }
  if ($p -match '^\d+$')       { return [int]$p }
  throw "Unrecognized PR identifier: '$p'"
}
function Get-LatestMergedPR([string]$base){
  $json = gh pr list --state merged --base $base --limit 1 --json number,mergedAt,title,headRefName,baseRefName 2>$null
  if (-not $json) { return $null }
  ($json | ConvertFrom-Json) | Select-Object -First 1
}
function Get-PRDetails([int]$nr){
  $json = gh pr view $nr --json number,title,body,mergeCommit,mergedAt,baseRefName,headRefName,url 2>$null
  if (-not $json) { throw "Unable to fetch PR #$nr via gh." }
  $o = $json | ConvertFrom-Json
  if (-not $o.mergeCommit) { throw "PR #$nr has no mergeCommit (not merged yet?)." }
  return $o
}
function New-AutoTagName {
  $tags = (git tag --list 'v1.0.*-auto') -split '\r?\n' | Where-Object { $_ }
  $max = 0
  foreach ($t in $tags) { if ($t -match '^v1\.0\.(\d+)-auto$') { $n = [int]$Matches[1]; if ($n -gt $max) { $max = $n } } }
  "v1.0.{0}-auto" -f ($max + 1)
}

Ensure-InRepo

$prNumber = Resolve-PRNumber $PR
if (-not $prNumber) {
  $latest = Get-LatestMergedPR $Branch
  if (-not $latest) { throw "No merged PRs found into '$Branch'." }
  $prNumber = [int]$latest.number
  Write-Host "Using latest merged PR into '$Branch': #$prNumber ($($latest.title))"
}

$details = Get-PRDetails $prNumber

# mergeCommit can be a string or an object { oid = ... } depending on gh version
$sha = $null
if ($details.mergeCommit -is [string]) { $sha = $details.mergeCommit }
elseif ($details.mergeCommit.PSObject.Properties.Name -contains 'oid') { $sha = $details.mergeCommit.oid }

if (-not $sha) { throw "Could not resolve merge commit SHA for PR #$prNumber." }

if (-not $Tag) { $Tag = New-AutoTagName }

Write-Host "Target merge commit: $sha"
Write-Host "Tag name           : $Tag"
Write-Host "PR                 : #$prNumber  $($details.url)"
Write-Host "Title              : $($details.title)"

$msgLines = @()
$msgLines += "$($details.title)"
$msgLines += ""
$msgLines += "PR: $($details.url)"
$body = ($details.body ?? '').Trim()
if ($body) { $msgLines += ""; $msgLines += $body }
$msg = $msgLines -join [Environment]::NewLine

if ($DryRun) {
  Write-Host "[DRY RUN] Would run:"
  Write-Host "  git tag -a $Tag $sha -m '<message>'"
  Write-Host "  git push origin $Tag"
  exit 0
}

git tag -a $Tag $sha -m $msg
git push origin $Tag
Write-Host "Tag pushed: $Tag -> $sha"