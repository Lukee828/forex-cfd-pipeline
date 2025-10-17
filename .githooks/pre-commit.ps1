#requires -Version 7
$ErrorActionPreference = 'Stop'
function Run-PreCommit {
  $cmd = Get-Command pre-commit -ErrorAction SilentlyContinue
  if ($cmd) {
    & $cmd.Path run --all-files
    exit $LASTEXITCODE
  }
  $venvPy = Join-Path (Join-Path \ '..') '.venv/Scripts/python.exe'
  if (Test-Path $venvPy) {
    & $venvPy -m pip install --disable-pip-version-check --quiet pre-commit | Out-Null
    & $venvPy -m pre_commit run --all-files
    exit $LASTEXITCODE
  }
  Write-Host "[pre-commit] pre-commit not found; skipping (no PATH cmd and no .venv)." -ForegroundColor Yellow
  exit 0
}
Run-PreCommit
