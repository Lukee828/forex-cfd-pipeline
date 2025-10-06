param(
  [string]$Python = ".\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"

# Make top-level package 'src' importable
$repoRoot = (Get-Location).Path
$env:PYTHONPATH = "$repoRoot" + ($(if ($env:PYTHONPATH) { ";" + $env:PYTHONPATH } else { "" }))

# compile sanity first
& $Python -m compileall -q src *> $null

# run smoke
$out = & $Python "tools\Smoke-VolState.py" 2>&1
$txt = [string]::Join("`n",$out)
if ($txt -notmatch "VOLSTATE_OK") {
  $out | Select-Object -First 80 | Write-Host
  throw "VolState smoke failed."
}

Write-Host "VolState smoke OK ✅" -ForegroundColor Green
