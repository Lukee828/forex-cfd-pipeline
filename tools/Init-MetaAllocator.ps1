$ErrorActionPreference="Stop"
Set-Location "C:\Users\speed\Desktop\forex-standalone"
$env:PYTHONPATH = "$PWD\src"
$py = Join-Path $PWD ".venv311\Scripts\python.exe"
if (!(Test-Path $py)) {
  $cmd = (Get-Command python -ErrorAction SilentlyContinue)
  if ($cmd) { $py = $cmd.Path }
  else { $py = "py"; $args = @("-3","-V"); & $py @args | Out-Null }
}
& $py -m pytest -q tests/alpha_factory/test_meta_allocator_smoke.py -vv --maxfail=1
