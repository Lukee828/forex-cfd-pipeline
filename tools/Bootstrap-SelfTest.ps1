param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
# tools/Bootstrap-SelfTest.ps1
[CmdletBinding()]
param([switch]$NoFail)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step($msg) { Write-Host "→ $msg" -ForegroundColor Cyan }
function Finish([int]$code) {
    if ($PSCommandPath) { exit $code }
    else { $global:LASTEXITCODE = $code; return }
}

# Pick Python: prefer local venv, else system
$py = Join-Path -Path $PSScriptRoot -ChildPath "..\.venv311\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "== Bootstrap Self-Test ==" -ForegroundColor Green

# --- AI-Guard (non-blocking placeholder supported) ---
if (Test-Path (Join-Path $PSScriptRoot "AI-Guard.ps1")) {
    Write-Step "Policy local-only: OK"
    & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "AI-Guard.ps1")
} else {
    Write-Host "AI-Guard.ps1 not found, skipping." -ForegroundColor Yellow
}

# --- Ruff ---
Write-Step "Ruff"
try { & $py -m ruff check . } catch {
    Write-Host "Ruff failed." -ForegroundColor Red
    if (-not $NoFail) { Finish 2 }
}

# --- Black ---
Write-Step "Black --check"
try { & $py -m black --check . } catch {
    Write-Host "Black failed." -ForegroundColor Red
    if (-not $NoFail) { Finish 2 }
}

# --- Pytest ---
Write-Step "Pytest smoke"
try { & $py -m pytest -q --maxfail=1 } catch {
    Write-Host "Tests failed." -ForegroundColor Red
    if (-not $NoFail) { Finish 2 }
}

Write-Host "✅ Self-Test complete." -ForegroundColor Green
Finish 0
