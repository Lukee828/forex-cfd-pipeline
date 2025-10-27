param(
  [string]$Repo = "." ,
  [string]$Metrics = "tools/_demo_metrics.json",
  [string]$Prev = "tools/_demo_prev.json",
  [string]$Corr = "tools/_demo_corr.json",
  [string]$Config = "configs/meta_allocator.json"
)
$ErrorActionPreference="Stop"
Set-Location $Repo
$env:PYTHONPATH = "$PWD\src"
$py = Join-Path $PWD ".venv311\Scripts\python.exe"
if (!(Test-Path $py)) {
  $cmd = (Get-Command python -ErrorAction SilentlyContinue)
  if ($cmd) { $py = $cmd.Path } else { $py = "py" }
}
$outDir = Join-Path $PWD "artifacts\allocations"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$csv = Join-Path $outDir ($stamp + "_alloc.csv")

# run the runner.py directly (avoids -m import resolution issues)
& $py "src/alpha_factory/runner.py" --metrics $Metrics --prev $Prev --corr $Corr --config $Config --outcsv $csv
if ($LASTEXITCODE -ne 0) { throw "runner.py failed (exit $LASTEXITCODE)" }
if (!(Test-Path $csv)) { throw "expected CSV not found: $csv" }
Write-Host ("✔ wrote {0}" -f $csv) -ForegroundColor Green
