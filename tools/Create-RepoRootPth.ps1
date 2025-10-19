param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
# tools/Create-RepoRootPth.ps1  (PS7)
$ErrorActionPreference = "Stop"

# 1) Resolve repo root
$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) { $repoRoot = (Get-Location).Path }

# 2) Pick Python (prefer venv)
$py = @(
    (Join-Path $repoRoot ".venv/Scripts/python.exe")
    "python"
    "py"
) | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if (-not $py) { throw "Python not found in venv or PATH." }

# 3) Find site-packages
$site = & $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"

# 4) Write .pth pointing to repo root
$pthPath = Join-Path $site "repo_root.pth"
Set-Content -LiteralPath $pthPath -Value $repoRoot -Encoding ascii
Write-Host ("Wrote {0} -> {1}" -f $pthPath, $repoRoot) -ForegroundColor Green

# 5) Smoke check
& $py -c "import src, sys; print('src import OK:', list(getattr(src,'__path__',[])))"
