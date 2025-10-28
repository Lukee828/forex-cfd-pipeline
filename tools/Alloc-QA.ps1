Param(
  [ValidateSet("ewma","equal","bayes")] [string]$Mode = "ewma",
  [switch]$NoCI
)
$ErrorActionPreference = "Stop"
$root = (& git rev-parse --show-toplevel 2>$null); if (-not $root) { $root = (Get-Location).Path }
$src  = Join-Path $root "src"
$env:PYTHONPATH = $src
$py = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Path } else { $py = "python" }
  Write-Warning ("Using fallback Python: {0}" -f $py)
}
$outDir = Join-Path $root "artifacts/allocations"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
Write-Host ("PY:  {0}" -f $py) -ForegroundColor DarkCyan
Write-Host ("SRC: {0}" -f $src) -ForegroundColor DarkCyan
& $py -m alpha_factory.cli_meta_alloc --mode $Mode --metrics "configs/meta_metrics.json" --outdir $outDir --write-latest
if ($LASTEXITCODE -ne 0) { throw ("cli_meta_alloc exit {0}" -f $LASTEXITCODE) }
Write-Host "`n== Outputs ==" -ForegroundColor Cyan
Get-ChildItem $outDir -Filter "*_alloc.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Format-Table -Auto
$latest = Join-Path $outDir "latest.csv"
if (Test-Path $latest) { Write-Host "`nlatest.csv:" -ForegroundColor Cyan; Get-Content $latest }
if ($NoCI) { Write-Host "`n(NoCI set — skipping CI dispatch.)" -ForegroundColor Yellow; Write-Host "Done." -ForegroundColor Green; exit 0 }
$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) { Write-Warning "GitHub CLI not found; skipping CI dispatch."; Write-Host "Done." -ForegroundColor Green; exit 0 }
Write-Host "`n== Dispatch CI smoke ==" -ForegroundColor Cyan
$wf = ".github/workflows/meta-alloc-smoke.yml"
gh workflow run $wf | Out-Host
$rid = $null
for ($i=0; $i -lt 120 -and -not $rid; $i++) { Start-Sleep 1; $rid = gh run list --workflow $wf -L 1 --json databaseId --jq ".[0].databaseId" 2>$null }
if (-not $rid) { throw "No run appeared for $wf." }
for ($i=0; $i -lt 240; $i++) {
  $meta = gh run view $rid --json status,conclusion,url | ConvertFrom-Json
  Write-Host ("Run: {0} | status={1} | conclusion={2}" -f $meta.url,$meta.status,$meta.conclusion)
  if ($meta.status -in @("completed","cancelled")) { break }
  Start-Sleep 2
}
$dest = Join-Path $root ("artifacts/ci-meta/" + $rid)
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
gh run download $rid --name allocations --dir $dest 2>$null
Write-Host "`n== CI artifact(s) ==" -ForegroundColor Cyan
if (Test-Path $dest) { Get-ChildItem $dest -Recurse | Format-Table -Auto } else { Write-Warning "No artifact folder created." }
Write-Host "Done." -ForegroundColor Green
