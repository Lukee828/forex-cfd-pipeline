param(
  [Parameter()][string]$Branch = "",
  [Parameter(Mandatory)][string]$Title,
  [Parameter(Mandatory)][string]$Notes,
  [string]$Tag = ""
)
$ErrorActionPreference = "Stop"

# Branch: auto-generate if not provided
if (-not $Branch -or $Branch.Trim().Length -eq 0) {
  $slug = ($Title -replace '[^\w\-]+','-').Trim('-').ToLower()
  if (-not $slug) { $slug = "feature" }
  $Branch = "auto/{0}-{1}" -f $slug, (Get-Date -Format "yyyyMMdd-HHmm")
}

# Create/switch branch (idempotent)
git switch -c $Branch 2>$null | Out-Null
git switch $Branch | Out-Null

# Local hooks/tests (if present)
if (Test-Path .\.venv\Scripts\pre-commit.exe) { .\.venv\Scripts\pre-commit.exe run -a }
if (Test-Path .\.venv\Scripts\python.exe)    { .\.venv\Scripts\python.exe -m pytest -q }

# Ensure at least one commit (add tiny meta bump if nothing staged)
git add -A
$hasStaged = (git diff --cached --name-only) -ne $null
if (-not $hasStaged) {
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

# Create PR (or reuse existing)
$prNum = gh pr list --head $Branch --state open --json number -q '.[0].number' 2>$null
if (-not $prNum) {
  try {
    $prUrl = gh pr create --base main --head $Branch --title $Title --body $Notes 2>$null
    if ($prUrl -and ($prUrl -match '/pull/(\d+)$')) { $prNum = $Matches[1] }
    if (-not $prNum) {
      $prNum = gh pr list --head $Branch --state open --json number -q '.[0].number' 2>$null
    }
  } catch {
    Write-Host "Skipping PR creation: $($_.Exception.Message)" -ForegroundColor Yellow
  }
}
if (-not $prNum) { Write-Host "No PR opened (nothing to merge)."; return }
Write-Host ("PR #{0} opened/exists" -f $prNum) -ForegroundColor Cyan

# Wait for required checks (bounded)
$maxTries = 120  # ~10 minutes
for ($i = 0; $i -lt $maxTries; $i++) {
  $roll = gh pr view $prNum --json statusCheckRollup -q '.statusCheckRollup[].conclusion' 2>$null
  if ($roll -contains 'FAILURE') { throw "A required check failed." }
  if ($roll -and ($roll -notcontains $null) -and ($roll -notcontains 'PENDING')) { break }
  Start-Sleep -Seconds 5
}

# Merge: try auto first, fallback to manual
try {
  gh pr merge $prNum --squash --delete-branch --auto
  Write-Host ("Auto-merge scheduled for PR #{0}" -f $prNum) -ForegroundColor Green
} catch {
  try {
    gh pr merge $prNum --squash --delete-branch
    Write-Host ("Merged PR #{0}" -f $prNum) -ForegroundColor Green
  } catch {
    Write-Host "Merge blocked by policy; try: gh pr merge $prNum --squash --delete-branch --admin" -ForegroundColor Yellow
  }
}

# Optional tag & release
if ($Tag) {
  git switch main; git pull --ff-only
  if (-not (git tag -l $Tag)) {
    git tag $Tag; git push origin $Tag
  }
  $exists = gh release view $Tag --json tagName -q .tagName 2>$null
  if (-not $exists) {
    gh release create $Tag --title $Title --notes $Notes --latest
  }
  Write-Host ("Release ready: {0}" -f $Tag) -ForegroundColor Green
}
