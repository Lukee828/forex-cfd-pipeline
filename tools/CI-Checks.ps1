param([switch]$SmokeOnly)
$ErrorActionPreference = 'Stop'
$env:TZ = 'UTC'

Write-Host '→ Ruff' -ForegroundColor Cyan
python -m ruff check .

Write-Host '→ Black --check' -ForegroundColor Cyan
python -m black --check .

Write-Host '→ Pytest' -ForegroundColor Cyan
if ($SmokeOnly) {
  python -m pytest -q --maxfail=1 --disable-warnings tests/ci_smoke_test.py
} else {
  python -m pytest -q
}
