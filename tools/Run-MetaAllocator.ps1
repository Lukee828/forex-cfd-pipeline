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

# ensure src discoverable (redundant with shim, but helps when -m works)
$env:PYTHONPATH = "$PWD\src"

# build temp shim that forces src on sys.path and runs the module as __main__
$tmp = Join-Path $PWD "tools/_tmp_run_meta.py"
$src = (Resolve-Path (Join-Path $PWD "src")).Path
$pyLines = @()
$pyLines += 'import sys, runpy, os'
$pyLines += 'sys.path.insert(0, r"")'
$pyLines += 'runpy.run_module("alpha_factory.runner", run_name="__main__")'
Set-Content -Encoding UTF8 -Path $tmp -Value $pyLines

# pass CLI args to the runner through the shim
& $py $tmp --metrics $Metrics --prev $Prev --corr $Corr --config $Config
$code = $LASTEXITCODE
Remove-Item $tmp -ErrorAction SilentlyContinue
if ($code -ne 0) { throw "runner failed ($code)" }
