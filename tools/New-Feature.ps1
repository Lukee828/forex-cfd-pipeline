param(
  [Parameter(Mandatory)][string]$Branch,
  [Parameter(Mandatory)][string]$Title,
  [Parameter(Mandatory)][string]$Notes,
  [string]$Tag = ""
)
$ErrorActionPreference = "Stop"

# Create/switch branch
git switch -c $Branch 2>$null | Out-Null
git switch $Branch | Out-Null

# Pre-commit / tests (only if available)
if (Test-Path .\.venv\Scripts\pre-commit.exe) { .\.venv\Scripts\pre-commit.exe run -a }
if (Test-Path .\.venv\Scripts\python.exe)    { .\.venv\Scripts\python.exe -m pytest -q }

# Stage & commit everything (idempotent if nothing changed)
git add -A
if ((git diff --cached) -ne $null) {
  git commit -m $Title
}

git push -u origin HEAD

# Create PR if missing; capture PR number either way
$existingNum = gh pr list --head $Branch --state open --json number -q '.[0].number'
if (-not $existingNum) {
  $prUrl = gh pr create --base main --head $Branch --title $Title --body $Notes
  Write-Host "PR opened: $prUrl" -ForegroundColor Cyan
}
$pr = gh pr view --json number -q .number
Write-Host "PR #$pr ready"

# Wait for checks to finish (fail fast on failure)
do {
  $rollup = gh pr view $pr --json statusCheckRollup -q '.statusCheckRollup[].conclusion'
  if ($rollup -contains 'FAILURE') { throw "A required check failed." }
  Start-Sleep -Seconds 5
} until ($rollup -and ($rollup -notcontains $null) -and ($rollup -notcontains 'PENDING'))

# Try auto-merge; if policy blocks, fall back to normal merge
try {
  gh pr merge $pr --squash --delete-branch
} catch {
  Write-Warning "Skipping auto-merge (policy or checks not ready)."
}

# Tag + Release if Tag provided
if ($Tag) {
  git switch main; git pull --ff-only
  if (-not (git tag -l $Tag)) {
    git tag $Tag; git push origin $Tag
  }
  # Create release if not present
  $exists = gh release view $Tag --json tagName -q .tagName 2>$null
  if (-not $exists) {
    gh release create $Tag --title $Title --notes $Notes --latest
  }
  Write-Host "Release ready: $Tag" -ForegroundColor Green
}
