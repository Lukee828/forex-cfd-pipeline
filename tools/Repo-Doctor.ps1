param([switch]$StayOpen)
$ErrorActionPreference = "Stop"

function Ok($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

# 1) Python / venv sanity
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Err "Missing .venv"; exit 1 }
$ver = & $py -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
Ok "Python $ver"

# 2) Dependencies match lock
try {
  & $py -m piptools --version 2>$null
  if ($LASTEXITCODE -ne 0) { throw "piptools missing" }
  Ok "pip-tools present"
} catch {
  Warn "pip-tools not importable; install with: .\.venv\Scripts\pip install pip-tools"
}

# 3) Risk smoke suite
pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\Test-RiskSuite.ps1
if ($LASTEXITCODE -ne 0) { Err "RiskSuite failed"; exit 1 } else { Ok "RiskSuite OK" }

# 4) Pre-commit (format/lint)
try {
  & pre-commit --version 2>$null
  if ($LASTEXITCODE -ne 0) { throw "pre-commit missing" }
  & pre-commit run -a
  if ($LASTEXITCODE -ne 0) { Err "pre-commit issues"; exit 1 } else { Ok "pre-commit clean" }
} catch {
  Warn "pre-commit not found in PATH"
}

# 5) Git tree clean
$st = git status --porcelain
if ($st) { Warn "Unstaged changes:`n$st" } else { Ok "Git tree clean" }
