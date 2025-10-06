param(
  [string]$Python = ".\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"

# Ensure 'src' package is importable for the smoke script
$repoRoot = (Get-Location).Path
$env:PYTHONPATH = "$repoRoot" + ($(if ($env:PYTHONPATH) { ";" + $env:PYTHONPATH } else { "" }))

$out = & $Python "tools\Smoke-TimeStop.py" 2>&1
$out | Write-Host

$txt = [string]::Join("`n",$out)
if ($txt -notmatch 'CASE1 stop:\s*True' -or
    $txt -notmatch 'CASE2 stop:\s*False' -or
    $txt -notmatch 'CASE3 stop:\s*True')
{
  throw "TimeStop smoke failed."
}

Write-Host "`nTimeStop smoke OK ✅" -ForegroundColor Green
