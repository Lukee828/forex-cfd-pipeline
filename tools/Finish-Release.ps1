param(
  [Parameter(Mandatory=$true)]
  [string]$Tag,                 # e.g. v0.1.3

  [string]$RunPath,             # optional: specific run dir to use for preview
  [switch]$Publish,             # also upload assets (uses tools/Publish-Release.ps1)
  [switch]$ClosePR,             # close any open PR for current branch
  [switch]$NoPreview            # skip docs/equity.png update
)

$ErrorActionPreference = "Stop"

function Get-RepoSlug {
  if ($env:GITHUB_REPOSITORY -and $env:GITHUB_REPOSITORY -match "/") { return $env:GITHUB_REPOSITORY }
  $url = (git config --get remote.origin.url 2>$null)
  if (-not $url) { throw "Cannot detect git remote 'origin' URL." }
  if ($url -match 'github\.com[/:]([^/]+)/([^/\.]+)') { return "{0}/{1}" -f $matches[1], $matches[2] }
  throw "Unrecognized GitHub remote URL: $url"
}

function Get-LatestRunDir {
  $root = Join-Path $PSScriptRoot '..\runs'
  $runs = Get-ChildItem -Path $root -Recurse -Directory -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending
  if (-not $runs -or $runs.Count -eq 0) { throw "No run directories found under .\runs" }
  return $runs[0].FullName
}

function Get-PreviewPng {
  param([string]$PreferredDir)
  if ($PreferredDir) {
    $p = Join-Path $PreferredDir 'equity.png'
    if (Test-Path $p) { return $p }
  }
  $latest = Get-ChildItem -Path (Join-Path $PSScriptRoot '..\runs') -Recurse -Filter equity.png -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) { return $latest.FullName }
  return $null
}

# 0) Optional: publish/upload assets for $Tag (uses your working helper)
if ($Publish) {
  $pubScript = Join-Path $PSScriptRoot 'Publish-Release.ps1'
  if (-not (Test-Path $pubScript)) { throw "Missing tools/Publish-Release.ps1. Set -Publish:$false or restore the helper." }

  $runDir = if ($RunPath) { (Resolve-Path $RunPath).Path } else { Get-LatestRunDir }
  Write-Host "• Publishing release assets for $Tag (run dir: $runDir) ..."
  pwsh -File $pubScript -Tag $Tag -RunPath $runDir
}

# 1) Update docs/equity.png (unless skipped)
$png = $null
if (-not $NoPreview) {
  $png = Get-PreviewPng -PreferredDir $RunPath
  if ($png) {
    $dst = Join-Path $PSScriptRoot '..\docs\equity.png'
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) *> $null
    Copy-Item $png $dst -Force
    git add $dst
    if (-not (git status --porcelain)) {
      Write-Host "• docs/equity.png already up to date."
    } else {
      git commit -m "Docs: update equity preview for $Tag"
      git push
      Write-Host "• Updated and pushed docs/equity.png"
    }
  } else {
    Write-Warning "No equity.png found under runs — skipping preview update."
  }
}

# 2) Tag 'latest' to point at $Tag
Write-Host "• Updating 'latest' tag -> $Tag"
git tag -f latest $Tag
git push -f origin latest

# 3) Optionally close any open PR for current branch
if ($ClosePR) {
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Warning "gh CLI not found; cannot close PR. Install: https://github.com/cli/cli/releases"
  } else {
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    $repo = Get-RepoSlug
    $open = gh pr list --repo $repo --state open --head $branch --json number,title 2>$null | ConvertFrom-Json
    if ($open -and $open.Count -gt 0) {
      $num = $open[0].number
      $link = "https://github.com/{0}/releases/tag/{1}" -f $repo,$Tag
      gh pr close $num --repo $repo --delete-branch --comment "Merged via release $Tag — see assets: $link"
      Write-Host "• Closed PR #$num on $repo (branch $branch)"
    } else {
      Write-Host "• No open PR found for branch '$branch' — nothing to close."
    }
  }
}

# 4) Summary
$repoSlug = Get-RepoSlug
$relLink = "https://github.com/{0}/releases/tag/{1}" -f $repoSlug, $Tag
Write-Host ""
Write-Host "✔ Finish-Release complete."
Write-Host "   Release: $relLink"
if ($png) { Write-Host "   Preview copied from: $png" }
