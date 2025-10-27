param(
  [string]$Repo    = "$PSScriptRoot\..",
  [string]$Metrics = "tools/_demo_metrics.json",
  [string]$Prev    = "tools/_demo_prev.json",
  [string]$Corr    = "tools/_demo_corr.json",
  [string]$Config  = "configs/meta_allocator.json"
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path $Repo)
$env:PYTHONPATH = "$PWD\src"

# choose python
$py = Join-Path $PWD ".venv311\Scripts\python.exe"
if (!(Test-Path $py)) {
  $cmd = (Get-Command python -ErrorAction SilentlyContinue)
  $py  = if ($cmd) { $cmd.Path } else { "python" }
}
Write-Host "Using Python: $py"

# sanity
if (!(Test-Path $Metrics)) { throw "Missing metrics: $Metrics" }
if (!(Test-Path $Prev))    { throw "Missing prev: $Prev" }
if (!(Test-Path $Corr))    { throw "Missing corr: $Corr" }
if (!(Test-Path $Config))  { throw "Missing config: $Config" }

# run as module to satisfy relative imports
& $py -m alpha_factory.runner --metrics $Metrics --prev $Prev --corr $Corr --config $Config
if ($LASTEXITCODE -ne 0) { throw "runner failed ($LASTEXITCODE)" }
