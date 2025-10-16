#requires -version 7
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (git rev-parse --show-toplevel)

function Say($m,$fg='Gray'){ Write-Host $m -ForegroundColor $fg }

# 1) Informational cleanliness
if (git status --porcelain) {
  Say "[pre-push] Working tree not clean (info)." 'Yellow'
}

# 2) Repo-Doctor (blocking on failure if present)
if (Test-Path "tools/Repo-Doctor.ps1") {
  try { & ./tools/Repo-Doctor.ps1 -Quiet:$true -StopOnFail:$true | Out-Null }
  catch {
    Say "[pre-push] Repo-Doctor blocking: $($_.Exception.Message)" 'Red'
    exit 1
  }
} else {
  Say "[pre-push] tools/Repo-Doctor.ps1 not found (skipping)." 'DarkGray'
}

# 3) Zero-Touch (non-blocking if present)
if (Test-Path "tools/Zero-Touch.ps1") {
  try { & ./tools/Zero-Touch.ps1 -Quiet -NoWatch -NoDispatch | Out-Null }
  catch { Say "[pre-push] Zero-Touch warning: $($_.Exception.Message)" 'Yellow' }
} else {
  Say "[pre-push] tools/Zero-Touch.ps1 not found (skipping)." 'DarkGray'
}

# 4) Gentle nudge on .gitattributes
if (-not (Test-Path ".gitattributes")) {
  Say "[pre-push] .gitattributes missing (consider adding)." 'DarkYellow'
}

exit 0