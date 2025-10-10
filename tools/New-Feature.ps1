param(
  [Parameter(Mandatory)][string]$Branch,
  [Parameter(Mandatory)][string]$Title,
  [Parameter(Mandatory)][string]$Notes,
  [string]$Tag = ""
)
$ErrorActionPreference = "Stop"

# --- Branch setup (idempotent) ---
git switch -c $Branch 2>$null | Out-Null
git switch $Branch | Out-Null

# --- Optional hooks/tests ---
if (Test-Path .\.venv\Scripts\pre-commit.exe) { .\.venv\Scripts\pre-commit.exe run -a }
if (Test-Path .\.venv\Scripts\python.exe)    { .\.venv\Scripts\python.exe -m pytest -q }

# --- Ensure there is at least one commit on this branch ---
git add -A
$hasStaged = (git diff --cached --name-only) -ne $null
if (-not $hasStaged) {
  # create a tiny meta bump so branch has a commit
  $metaDir = Join-Path (Get-Location) ".meta"
  if (-not (Test-Path $metaDir)) { New-Item -ItemType Directory -Force -Path $metaDir | Out-Null }
  $ping = Join-Path $metaDir "nf-ping.txt"
  ("Ping {0:O}" -f (Get-Date)) | Out-File -Encoding utf8 -FilePath $ping
  git add $ping
}

# Commit if anything staged
if ((git diff --cached --name-only) -ne $null) {
  git commit -m $Title | Out-Null
}

# Push branch
git push -u origin HEAD

# --- Create PR (or reuse existing) ---
$pr = gh pr list --head $Branch --state open --json number -q '.[0].number'
if (-not $pr) {
  try {
    $pr = gh pr create --base main --head $Branch --title $Title --body $Notes --json number -q .number
  } catch {
    Write-Host "Skipping PR creation: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}

if (-not $pr) {
  Write-Host "No PR opened (likely no meaningful changes). Exiting without polling." -ForegroundColor Yellow
  return
}

Write-Host "PR #$pr opened/exists" -ForegroundColor Cyan

# --- Wait for checks (bounded) ---
$maxTries = 60  # ~5 min
for ($i = 0; $i -lt $maxTries; $i++) {
  $rollup = gh pr view $pr --json statusCheckRollup -q '.statusCheckRollup[].conclusion' 2>$null
  if ($rollup -contains 'FAILURE') { throw "A required check failed." }
  if ($rollup -and ($rollup -notcontains $null) -and ($rollup -notcontains 'PENDING')) { break }
  Start-Sleep -Seconds 5
}

# --- Merge (best effort) ---
try {
  gh pr merge $pr --squash --delete-branch
} catch {
  Write-Host "Skipping auto-merge (policy/checks not ready). You can merge from the PR page." -ForegroundColor Yellow
}

# --- Optional tag & release ---
if ($Tag) {
  git switch main; git pull --ff-only
  if (-not (git tag -l $Tag)) {
    git tag $Tag
    git push origin $Tag
  }
  if (-not (gh release view $Tag --json tagName -q .tagName 2>$null)) {
    gh release create $Tag --title $Title --notes $Notes --latest
  }
  Write-Host "Release ready: $Tag" -ForegroundColor Green
}
