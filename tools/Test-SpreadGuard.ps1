param(
  [string]$Python = ".\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"

$repoRoot = (Get-Location).Path
$env:PYTHONPATH = $repoRoot + ($(if ($env:PYTHONPATH) { ";" + $env:PYTHONPATH } else { "" }))

$out = & $Python "tools\Smoke-SpreadGuard.py" 2>&1
$txt = [string]::Join("`n", $out)

if ($txt -notmatch "Smoke-SpreadGuard OK") {
  $out | Select-Object -First 60 | Write-Host
  throw "SpreadGuard smoke failed."
}

Write-Host "SpreadGuard smoke OK ✅" -ForegroundColor Green
