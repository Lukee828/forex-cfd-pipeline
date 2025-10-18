param()
<# tools/Upload-LastRun.ps1 — Windows PowerShell 5.1 compatible

Usage examples:
  powershell -ExecutionPolicy Bypass -File tools\Upload-LastRun.ps1
  powershell -ExecutionPolicy Bypass -File tools\Upload-LastRun.ps1 -Tag v0.1.2
  powershell -ExecutionPolicy Bypass -File tools\Upload-LastRun.ps1 -RunPath ".\runs\backtest_20251001_204821"
#>

[CmdletBinding()]
param(
  [string]$Tag = "",
  [string]$RunPath = "",
  [switch]$NoZip
)

$ErrorActionPreference = 'Stop'

function Require-Cli([string]$name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Required CLI '$name' not found in PATH."
  }
}

function Get-RepoRoot() {
  try {
    $root = (git rev-parse --show-toplevel).Trim()
    if ($root) { return $root }
  } catch { }
  # Fallback: current directory
  return (Resolve-Path ".").Path
}

function Get-LatestTag() {
  try {
    $t = (git describe --tags --abbrev=0 2>$null).Trim()
    if ($t) { return $t }
  } catch { }
  return ""
}

function Ensure-Tag([string]$t) {
  if (-not $t) { return "" }
  $exists = $false
  try {
    git rev-parse -q --verify "refs/tags/$t" *> $null
    if ($LASTEXITCODE -eq 0) { $exists = $true }
  } catch { }
  if (-not $exists) {
    git tag -a $t -m "Release $t at $(Get-Date -Format s)"
    git push origin $t
  }
  return $t
}

function Ensure-Release([string]$t) {
  if (-not $t) { return }
  $relExists = $false
  try {
    & gh release view $t *> $null
    if ($LASTEXITCODE -eq 0) { $relExists = $true }
  } catch { }
  if (-not $relExists) {
    & gh release create $t --title $t --notes "Automated artifacts for $t"
  }
}

function Find-LatestRunDir([string]$repoRoot) {
  $runs = Join-Path $repoRoot "runs"
  if (-not (Test-Path $runs)) { throw "No 'runs' directory at '$runs'." }
  $dirs = Get-ChildItem -LiteralPath $runs -Directory -Filter "backtest_*" | Sort-Object LastWriteTime -Descending
  if (-not $dirs -or $dirs.Count -eq 0) { throw "No 'runs\backtest_*' directories found." }
  return $dirs[0].FullName
}

function New-Zip([string]$sourceDir, [string]$zipPath) {
  if ($NoZip) { return $null }
  try {
    # Prefer built-in Compress-Archive on PS 5.1
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path (Join-Path $sourceDir '*') -DestinationPath $zipPath -Force
    return $zipPath
  } catch {
    # Fallback to .NET ZipFile::CreateFromDirectory (Framework)
    try {
      Add-Type -AssemblyName System.IO.Compression.FileSystem
      if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
      [System.IO.Compression.ZipFile]::CreateFromDirectory($sourceDir, $zipPath)
      return $zipPath
    } catch {
      throw "Zipping failed with both Compress-Archive and ZipFile. $_"
    }
  }
}

# --- Checks ---
Require-Cli git
Require-Cli gh

# --- Resolve repo root & run dir ---
$repoRoot = Get-RepoRoot
if ($RunPath) {
  $runDir = (Resolve-Path $RunPath).Path
} else {
  $runDir = Find-LatestRunDir $repoRoot
}
if (-not (Test-Path $runDir)) { throw "Run directory not found: $runDir" }
Write-Host "Using run dir: $runDir"

# --- Tag & Release ---
if (-not $Tag) { $Tag = Get-LatestTag }
if (-not $Tag) { $Tag = "v0.1.0" }
$Tag = Ensure-Tag $Tag
Ensure-Release $Tag

# --- Collect files ---
$files = Get-ChildItem -LiteralPath $runDir -File
if (-not $files -or $files.Count -eq 0) { throw "No files in '$runDir'." }
$equity = $files | Where-Object { $_.Name -like "equity*.png" } | Select-Object -First 1

# --- Zip artifacts (unless -NoZip) ---
$upload = @()
if (-not $NoZip) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $zipName = "backtest_artifacts_$($Tag.TrimStart('v'))_$ts.zip"
  $zipPath = Join-Path $runDir $zipName
  $zipMade = New-Zip -sourceDir $runDir -zipPath $zipPath
  if ($zipMade) { $upload += $zipMade }
} else {
  $upload += ($files | ForEach-Object { $_.FullName })
}

if ($equity) { $upload += $equity.FullName }

# --- Upload ---
Write-Host "`nUploading $($upload.Count) asset(s) to $Tag ..."
foreach ($p in $upload) {
  & gh release upload $Tag $p --clobber
  if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to upload: $p" }
}

$repo = (& gh repo view --json nameWithOwner -q ".nameWithOwner").Trim()
if (-not $repo) { $repo = "(unknown repo)" }
$releaseUrl = "https://github.com/$repo/releases/tag/$Tag"
Write-Host "`n✔ Done. Release: $releaseUrl"
if ($equity) { Write-Host "   Preview image: $($equity.Name)" }

