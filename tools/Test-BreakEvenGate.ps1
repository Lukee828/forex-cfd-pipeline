param(
  [string]$Python = ".\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"

# Ensure package discovery from repo root (so src.* works from tools/)
$repoRoot = (Get-Location).Path
$env:PYTHONPATH = "$repoRoot" + ($(if ($env:PYTHONPATH) { ";" + $env:PYTHONPATH } else { "" }))

$out = & $Python "tools\Smoke-BreakEvenGate.py" 2>&1
$out | Write-Host

$txt = [string]::Join("`n",$out)
if ($txt -notmatch 'CASE1 arm:\s*True' -or
    $txt -notmatch 'CASE2 arm:\s*False' -or
    $txt -notmatch 'CASE3 arm:\s*True' -or
    $txt -notmatch 'SIGN test long/short:')
{
  throw "BreakEvenGate smoke failed."
}

Write-Host "`nBreakEvenGate smoke OK ✅" -ForegroundColor Green
