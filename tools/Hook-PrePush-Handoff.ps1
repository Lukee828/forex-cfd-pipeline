# tools/Hook-PrePush-Handoff.ps1
# Blocks push if repo state is inconsistent with ai_lab/state.json (or lock active).

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Ensure we run from repo root
$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) {
  Write-Host "Not a git repo; allowing push." -ForegroundColor Yellow
  exit 0
}
Set-Location $root

# 1) Optional: read-only audit (won't modify files)
try {
  pwsh -NoProfile -ExecutionPolicy Bypass -File "$root/tools/Audit-State.ps1" | Out-Host
} catch {
  Write-Host "Audit script failed (non-fatal); continuing to Strict handoff..." -ForegroundColor Yellow
}

# 2) Strict handoff check (this is the gate)
pwsh -NoProfile -ExecutionPolicy Bypass -File "$root/tools/Make-Handoff.ps1" `
  -Strict `
  -WithLogs `
  -Logs 5 `
  -ToFile "ai_lab/handoff_latest.md" | Out-Host

if ($LASTEXITCODE -ne 0) {
  Write-Host "❌ Pre-push blocked: handoff warnings present. See ai_lab/handoff_latest.md." -ForegroundColor Red
  exit 1
}

Write-Host "✅ Pre-push OK: handoff clean." -ForegroundColor Green
exit 0
