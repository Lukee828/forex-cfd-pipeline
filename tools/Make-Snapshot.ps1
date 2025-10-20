[CmdletBinding()]
param(
  [string]$Label = "",
  [switch]$IncludeUntracked
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
  if (Get-Command git -ErrorAction SilentlyContinue) {
    try {
      $root = (git -C $PWD rev-parse --show-toplevel).Trim()
      if ($root) { return $root }
    } catch {}
  }
  return (Get-Location).Path
}

$repoRoot = Get-RepoRoot

# Metadata (best-effort if git exists)
$stamp  = (Get-Date).ToString('yyyyMMdd-HHmmss')
$branch = ""
$sha    = ""
if (Get-Command git -ErrorAction SilentlyContinue) {
  try { $branch = (git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim() } catch {}
  try { $sha    = (git -C $repoRoot rev-parse --short HEAD).Trim() } catch {}
}

$name = "snapshot_$stamp"
if ($branch) { $name += "_$branch" }
if ($sha)    { $name += "_$sha" }
if ($Label)  { $name += "_$Label" }

$outDir  = Join-Path $repoRoot "_snapshot"
$zipPath = Join-Path $outDir ($name + ".zip")
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

# Build file list
$files = @()
if (Get-Command git -ErrorAction SilentlyContinue) {
  $files += (git -C $repoRoot ls-files)
  if ($IncludeUntracked) {
    $files += (git -C $repoRoot ls-files --others --exclude-standard)
  }
  $files = $files | Where-Object { $_ } | Sort-Object -Unique
} else {
  $files = Get-ChildItem -File -Recurse -Path $repoRoot |
           Where-Object { $_.FullName -notmatch '\\\.git\\' } |
           ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1) }
}

# Create ZIP
Add-Type -AssemblyName System.IO.Compression.FileSystem
$fs  = [System.IO.File]::Create($zipPath)
$zip = [System.IO.Compression.ZipArchive]::new($fs, [System.IO.Compression.ZipArchiveMode]::Create, $false)

function Add-TextEntry([System.IO.Compression.ZipArchive]$Zip, [string]$Path, [string]$Text) {
  $entry = $Zip.CreateEntry($Path)
  $sw = [System.IO.StreamWriter]::new($entry.Open())
  try { $sw.Write($Text) } finally { $sw.Dispose() }
}

# Add files
foreach ($rel in $files) {
  $full = Join-Path $repoRoot $rel
  if (-not (Test-Path $full)) { continue }
  $entry = $zip.CreateEntry($rel, [System.IO.Compression.CompressionLevel]::Optimal)
  $in  = [System.IO.File]::OpenRead($full)
  $out = $entry.Open()
  try { $in.CopyTo($out) } finally { $in.Dispose(); $out.Dispose() }
}

# Add metadata
$meta = @"
repoRoot: $repoRoot
timestamp: $stamp
branch: $branch
commit: $sha
label: $Label
include_untracked: $IncludeUntracked
file_count: $($files.Count)
"@
Add-TextEntry -Zip $zip -Path "SNAPSHOT_INFO.txt" -Text $meta

$zip.Dispose()
$fs.Dispose()

Write-Host "✔ Snapshot created:" -ForegroundColor Green
Write-Host "  $zipPath"
