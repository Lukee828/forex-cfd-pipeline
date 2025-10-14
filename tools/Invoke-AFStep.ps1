Param(
  [Parameter(Mandatory)][string]$Branch,
  [Parameter(Mandatory)][string]$Title,
  [Parameter(Mandatory)][string]$Body,
  [string[]]$StagePaths = @("zigzagob","tests"),
  [string[]]$PyTests = @(),            # e.g. "tests/store/test_feature_store.py -q"
  [string]$Label = "infra"
)

$py = ".\.venv311\Scripts\python.exe"
function Run-Py { param([string[]]$Args) & $py -m $Args; if ($LASTEXITCODE) { throw "Python cmd failed: $Args" } }
function Safe-Git { param([string[]]$Args) git @Args; if ($LASTEXITCODE) { throw "git failed: $Args" } }

Write-Host "[AF] Branch => $Branch" -ForegroundColor Cyan
try {
  Safe-Git @(''switch'', ''-c'', $Branch)
} catch {
  Write-Host "[AF] Branch may already exist; switching..." -ForegroundColor Yellow
  Safe-Git @(''switch'', $Branch)
}

# Smoke tests before commit (optional)
foreach ($t in $PyTests) { if ($t) { Run-Py @("pytest", $t) } }

# Stage + initial commit
Safe-Git add --all -- $StagePaths
try {
  Safe-Git @(''switch'', ''-c'', $Branch)
} catch {
  Write-Host "[AF] Branch may already exist; switching..." -ForegroundColor Yellow
  Safe-Git @(''switch'', $Branch)
}

# Pre-commit may rewrite files. If so, re-stage & commit once more.
$pc = (git status --porcelain)
if ($pc) {
  Write-Host "[AF] Pre-commit rewrote files; re-staging..." -ForegroundColor Yellow
  Safe-Git add -A
  try {
  Safe-Git @(''switch'', ''-c'', $Branch)
} catch {
  Write-Host "[AF] Branch may already exist; switching..." -ForegroundColor Yellow
  Safe-Git @(''switch'', $Branch)
}
}

# Push branch
Safe-Git push -u origin $Branch

# Ensure label exists; ignore errors if already present
gh label create $Label --color BFD4F2 --description "Infrastructure modules" 2>$null

# Create PR, label, auto-merge
$pr = gh pr create --base main --head $Branch --title $Title --body $Body
Write-Host $pr
gh pr edit --add-label $Label 2>$null
gh pr merge --auto --squash --delete-branch
