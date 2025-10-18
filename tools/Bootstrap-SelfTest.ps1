param()
$ErrorActionPreference = "Stop"

# Skip on non-Windows
if (-not $IsWindows) {
  Write-Host "Bootstrap-SelfTest: skipping on non-Windows runner."
  exit 0
}

Write-Host "== Bootstrap Self-Test ==" -ForegroundColor Cyan

# YAML policy check only if ConvertFrom-Yaml exists
if (Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue) {
  $policy = Get-Content policy.yaml -Raw | ConvertFrom-Yaml
  if (-not $policy.network.no_network) {
    Write-Host "no_network must be true" -ForegroundColor Red
    exit 1
  }
  Write-Host "Policy local-only: OK" -ForegroundColor Green
} else {
  Write-Warning "ConvertFrom-Yaml not available; skipping YAML checks."
}

# Resolve path to AI-Guard.ps1 in a way that works in CI and locally
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $PSCommandPath }
if (-not $here) { $here = (Resolve-Path "./tools").Path }

& (Join-Path $here "AI-Guard.ps1")
Write-Host "== All checks passed ==" -ForegroundColor Green
