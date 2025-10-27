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

# ensure src discoverable
$env:PYTHONPATH = (Resolve-Path (Join-Path $PWD "src")).Path
Write-Host "PYTHONPATH=$env:PYTHONPATH"

# bootstrap via runpy and explicit argv
$code = 0
try {
  & $py -c "import sys, os, runpy; sys.path.insert(0, os.path.abspath(r'$($env:PYTHONPATH)')); sys.argv = ['alpha_factory.runner', '--metrics', r'$($Metrics)', '--prev', r'$($Prev)', '--corr', r'$($Corr)', '--config', r'$($Config)']; runpy.run_module('alpha_factory.runner', run_name='__main__')"
  $code = $LASTEXITCODE
} catch { $code = 1 }
if ($code -ne 0) { throw "runner failed ($code)" }
