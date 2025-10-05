param(
  [Parameter(Mandatory=$true)][string]$Tag,
  [Parameter(Mandatory=$false)][string]$RunPath
)

$ErrorActionPreference = 'Stop'

function Get-RepoSlug {
  $url = git config --get remote.origin.url 2>$null
  if (-not $url) { throw "Cannot detect git remote 'origin' URL." }
  if ($url -match 'github\.com[/:]([^/]+)/([^/\.]+)') {
    return "{0}/{1}" -f $matches[1], $matches[2]
  }
  throw "Unrecognized GitHub remote URL: $url"
}

function Get-LatestRunDir {
  $root = Join-Path $PSScriptRoot '..\runs'
  $runs = Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending
  if (-not $runs -or $runs.Count -eq 0) { throw "No run directories found under .\runs" }
  return $runs[0].FullName
}

function New-ZipFromDir {
  param(
    [Parameter(Mandatory=$true)][string]$SourceDir,
    [Parameter(Mandatory=$true)][string]$DestZipPath
  )
  if (Test-Path $DestZipPath) { Remove-Item $DestZipPath -Force }
  Compress-Archive -Path (Join-Path $SourceDir '*') -DestinationPath $DestZipPath -Force
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI 'gh' not found. Install: https://github.com/cli/cli/releases"
}

$runDir = if ($RunPath) { (Resolve-Path $RunPath).ToString() } else { Get-LatestRunDir }
Write-Host "Using run dir: $runDir"

$assets = @()
foreach ($p in 'equity.png','equity.csv','portfolio_returns.csv','closes.csv') {
  $full = Join-Path $runDir $p
  if (Test-Path $full) { $assets += $full }
}

$zipPath = Join-Path $runDir ("{0}.zip" -f (Split-Path $runDir -Leaf))
New-ZipFromDir -SourceDir $runDir -DestZipPath $zipPath
$assets += $zipPath

if ($assets.Count -eq 0) { throw "No assets found to upload in $runDir" }

$repo = Get-RepoSlug
$exists = (gh release view $Tag --repo $repo *> $null; $LASTEXITCODE -eq 0)

if (-not $exists) {
  Write-Host "Creating release $Tag ..."
  gh release create $Tag --repo $repo --title $Tag --notes "Automated release for $Tag" --latest --verify-tag *> $null
} else {
  Write-Host "Release $Tag exists — uploading assets (clobber)."
}

Write-Host ("Uploading {0} asset(s) to {1} ..." -f $assets.Count,$Tag)
gh release upload $Tag $assets --clobber --repo $repo *> $null

Write-Host ""
Write-Host ("Done: https://github.com/{0}/releases/tag/{1}" -f $repo,$Tag)
if (Test-Path (Join-Path $runDir 'equity.png')) { Write-Host "Preview image: equity.png" }
