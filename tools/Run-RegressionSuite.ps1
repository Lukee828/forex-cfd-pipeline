#requires -Version 7
$ErrorActionPreference = "Stop"
$Py = ".venv/Scripts/python.exe"; if (-not (Test-Path $Py)) { $Py = "python" }
$root = (Resolve-Path ".").Path
$old = $env:PYTHONPATH; $env:PYTHONPATH = "$root;$root\src"
try {
  & $Py -m src.qa.regression_suite
} finally {
  $env:PYTHONPATH = $old
}
