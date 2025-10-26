param(
  [string]$Label = 'snapshot',
  [switch]$IncludeUntracked
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (git rev-parse --show-toplevel)
$dstDir = Join-Path $root 'ai_lab/snapshots'
$null = New-Item -ItemType Directory -Path $dstDir -Force
$ts = (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss')
$zip = Join-Path $dstDir ("$ts-$Label.zip")

# tracked files (HEAD) via git archive -> tar -> expand
$tarTmp = Join-Path $env:TEMP ("snap-$ts.tar")
& git -c core.autocrlf=false archive -o $tarTmp HEAD
$workTmp = Join-Path $env:TEMP ("snap-$ts-work")
if (Test-Path $workTmp) { Remove-Item -Recurse -Force $workTmp }
$null = New-Item -ItemType Directory -Path $workTmp -Force
& tar -xf $tarTmp -C $workTmp

if ($IncludeUntracked) {
  $untracked = git ls-files --others --exclude-standard | Where-Object {
    $_ -and $_ -notlike '.pre-commit-cache*' -and $_ -notlike 'ai_lab/snapshots*'
  }
  foreach ($f in $untracked) {
    $src = Join-Path $root $f
    $dst = Join-Path $workTmp $f
    New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
    if (Test-Path $src) {
      $item = Get-Item $src
      if ($item.PSIsContainer) { Copy-Item $src $dst -Recurse -Force } else { Copy-Item $src $dst -Force }
    }
  }
}
Compress-Archive -Path (Join-Path $workTmp '*') -DestinationPath $zip -Force
Remove-Item $workTmp -Recurse -Force; Remove-Item $tarTmp -Force
Write-Host "✔ Snapshot: $zip" -ForegroundColor Green
