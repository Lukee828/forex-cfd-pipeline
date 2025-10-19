param()
#requires -Version 7.0
param(
  [int]$Number,
  [switch]$Rebase,
  [switch]$AdminMerge
)
$ErrorActionPreference = 'Stop'

# Infer PR number silently if not provided
if (-not $PSBoundParameters.ContainsKey('Number')) {
  $n = $null
  if ($env:PR_NUMBER -and [int]::TryParse($env:PR_NUMBER, [ref]$n)) {
    $Number = $n
  } else {
    try {
      $branch = (git rev-parse --abbrev-ref HEAD).Trim()
      $cand = gh pr list --head $branch --state open --json number -q '.[0].number' 2>$null
      if ($cand) { $Number = [int]$cand }
    } catch { }
    if (-not $Number) {
      try {
        $cand = gh pr status --json currentPR -q .currentPR.number 2>$null
        if ($cand) { $Number = [int]$cand }
      } catch { }
    }
  }
  if (-not $Number) { exit 2 }
}

# Resolve PR head branch
$headBranch = gh pr view $Number --json headRefName -q .headRefName
if (-not $headBranch) { exit 3 }

# Checkout PR branch
gh pr checkout $Number | Out-Null

# Ensure no editor is invoked
$env:GIT_EDITOR = "true"
$env:GIT_SEQUENCE_EDITOR = "true"
$env:GIT_MERGE_AUTOEDIT = "no"

# Sync with latest main (non-interactive)
git fetch origin main | Out-Null
if ($Rebase) {
  git -c core.editor=true rebase origin/main
} else {
  git -c core.editor=true merge origin/main --no-edit
}

# Stop if conflicts remain
if (git ls-files -u) { exit 4 }

# Commit if needed (covers clean merges)
if ((git status --porcelain) -match '^[AMR]') {
  git add -A
  git commit -m "chore: conflict repair for PR #$Number" | Out-Null
}

# Push (force-with-lease if rebase)
if ($Rebase) { git push --force-with-lease } else { git push }

# Queue merge
try {
  gh pr merge $Number --squash --delete-branch --auto
} catch {
  if ($AdminMerge) {
    gh pr merge $Number --squash --delete-branch --admin
  } else {
    throw
  }
}
