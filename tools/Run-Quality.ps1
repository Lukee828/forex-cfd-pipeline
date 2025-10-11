$ErrorActionPreference = "Stop"; Set-StrictMode -Version Latest
$repo = (git rev-parse --show-toplevel) 2>$null
if (-not $repo) { throw "Run inside the git repo root." }
Set-Location $repo

$ok = $true

if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
  pre-commit run -a | Out-Host
  if ($LASTEXITCODE -ne 0) { $ok = $false }
} else {
  Write-Host "⚠ pre-commit not found; skipping hooks" -ForegroundColor Yellow
}

if (Get-Command pytest -ErrorAction SilentlyContinue) {
  pytest -q
  if ($LASTEXITCODE -ne 0) { $ok = $false }
} else {
  Write-Host "⚠ pytest not found; skipping tests" -ForegroundColor Yellow
}

if ($ok) { Write-Host "✅ Hooks & tests green." -ForegroundColor Green; exit 0 }
Write-Host "❌ Hooks and/or tests failed. See output above." -ForegroundColor Red; exit 1
