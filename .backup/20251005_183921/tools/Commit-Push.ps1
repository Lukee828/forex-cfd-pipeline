param(
  [Parameter(Mandatory=$true)][string]$Message
)
$ErrorActionPreference = "Stop"

# Normalize endings once per run (optional, harmless if already set)
git config core.autocrlf false
git config core.eol lf

# Stage → run hooks → stage again (to catch auto-fixes) → commit → push
git add -A
try {
  pre-commit run --all-files
} catch {
  Write-Warning "pre-commit reported issues; attempting to continue after auto-fixes..."
}
git add -A

# Commit (handle "nothing to commit" cleanly)
$commitNeeded = git diff --cached --name-only
if (-not $commitNeeded) {
  Write-Host "Nothing to commit; working tree clean."
  exit 0
}

git commit -m $Message
git push
Write-Host "✔ Pushed: $Message"
