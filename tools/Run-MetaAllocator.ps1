param(
  [string]$Repo    = "$PSScriptRoot\..",
  [string]$Metrics = "tools/_demo_metrics.json",
  [string]$Prev    = "tools/_demo_prev.json",
  [string]$Corr    = "tools/_demo_corr.json",
  [string]$Config  = "configs/meta_allocator.json"
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path $Repo)

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

# ensure src is discoverable
$env:PYTHONPATH = (Resolve-Path (Join-Path $PWD "src")).Path
Write-Host "PYTHONPATH=$env:PYTHONPATH"

# quick import probe (optional, fast)
& $py -c "import sys; import importlib; sys.path.insert(0, r'$($env:PYTHONPATH)'.strip()); importlib.import_module('alpha_factory.runner'); print('import_ok')"
if ($LASTEXITCODE -ne 0) { throw "import probe failed" }

# run the runner as a module
& $py -m alpha_factory.runner --metrics $Metrics --prev $Prev --corr $Corr --config $Config
if ($LASTEXITCODE -ne 0) { throw "runner failed ($LASTEXITCODE)" }
