param(
  [string]$Python = ".\.venv311\Scripts\python.exe",
  [string]$SrcPath = ".\src"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
if (-not (Test-Path $Python)) { throw "Python not found at: $Python" }
$srcAbs = (Resolve-Path $SrcPath).Path
if (-not (Test-Path $srcAbs)) { throw "Src path not found: $srcAbs" }
$site = & $Python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
if ($LASTEXITCODE -ne 0 -or -not $site) { throw "Could not locate site-packages via Python." }
$site = $site.Trim()
$pth = Join-Path $site "alpha_factory_repo.pth"
[IO.File]::WriteAllText($pth, ($srcAbs + "`n"), (New-Object System.Text.UTF8Encoding($false)))
Ok "Wrote .pth → $pth"
Info "Now Python will always see: $srcAbs"
