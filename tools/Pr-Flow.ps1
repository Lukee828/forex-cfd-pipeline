param(
  [Parameter(Mandatory=$true)][string]$Branch,
  [Parameter(Mandatory=$true)][string]$Title,
  [string]$Body = "",
  [switch]$MakeWip
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Say($m){ Write-Host $m -ForegroundColor Cyan }
function Die($m){ Write-Host $m -ForegroundColor Red; exit 1 }

if (-not (Get-Command git -ea SilentlyContinue)) { Die "git not found" }
if (-not (Get-Command gh  -ea SilentlyContinue)) { Die "gh not found"  }

# Ensure branch exists & checked out
if (-not (git rev-parse --verify $Branch 2>$null)) { git switch -c $Branch | Out-Null } else { git switch $Branch | Out-Null }

git fetch origin | Out-Null

# Count ahead/behind vs origin/main
$counts = (git rev-list --left-right --count origin/main...HEAD).Trim().Split()
[int]$behind = $counts[0]; [int]$ahead = $counts[1]
Say ("Ahead={0} Behind={1}" -f $ahead,$behind)

# If not ahead, optionally create a tiny WIP commit
if ($ahead -eq 0) {
  if ($MakeWip) {
    ni docs -ea 0 | Out-Null
    $note = "WIP placeholder for $Branch at $(Get-Date -AsUTC)"
    Set-Content -Path ("docs/wip-{0}.md" -f ($Branch -replace '[^\w\-]','-')) -Value $note
    git add -A
    git commit -m ("docs: add WIP for {0}" -f $Branch) | Out-Null
    $ahead = 1
  } else {
    Die "Branch '$Branch' has no commits ahead of main. Make a commit or re-run with -MakeWip."
  }
}

git push -u origin $Branch | Out-Null

# Create PR
$prUrl = gh pr create --base main --head $Branch --title $Title --body $Body
if ($prUrl -match '/pull/(\d+)$') { $pr = [int]$Matches[1] } else { $pr = gh pr list --head $Branch --state open --json number -q '.[0].number' }
Say ("PR #{0}" -f $pr)

# Queue auto-merge
gh pr merge $pr --squash --delete-branch --auto | Out-Null
Say "Auto-merge queued."

# Watch the newest PR run if present
$run = gh run list --branch $Branch --event pull_request --limit 1 --json databaseId -q '.[0].databaseId' 2>$null
if ($run) {
  Say ("Watching run {0}…" -f $run)
  gh run watch $run --exit-status
} else {
  Say "No PR run yet (that’s OK if your repo doesn’t run tests on PRs)."
}

# Return to main and fast-forward
git switch main | Out-Null
git pull --ff-only
Say "Done."
