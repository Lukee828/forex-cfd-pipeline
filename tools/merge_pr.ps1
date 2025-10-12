param(
  [Alias("Id")][string]$PR,
  [ValidateSet("merge","rebase","squash")][string]$Strategy = "squash",
  [switch]$DeleteBranch,
  [switch]$Auto,
  [switch]$Sync
)

function Fail($msg){ Write-Error $msg; exit 1 }

# Infer PR from current branch if -Id not provided
if (-not $PR) {
  $inferred = (& gh pr view --json number --jq ".number" 2>$null)
  if ($LASTEXITCODE -eq 0 -and $inferred) {
    $PR = $inferred
    Write-Host "→ Inferred PR #$PR from current branch"
  } else {
    Fail "No -Id provided and unable to infer a PR for the current branch."
  }
}

Write-Host "→ PR #$PR status:"
$viewArgs = @(
  "pr","view","$PR",
  "",
  "--json","title,headRefName,baseRefName,state",
  "--template","  {{.title}}  ({{.state}})  head={{.headRefName}} -> base={{.baseRefName}}"
)
$status = & gh @viewArgs 2>$null
if ($LASTEXITCODE -eq 0 -and $status) { Write-Host $status } else { Write-Warning "Unable to query PR status (gh exit $LASTEXITCODE)." }

$mergeArgs = @("pr","merge","$PR","--$Strategy")
if ($DeleteBranch) { $mergeArgs += "--delete-branch" }
if ($Auto)         { $mergeArgs += "--auto" }

Write-Host "→ Running: gh $($mergeArgs -join ' ')"
& gh @mergeArgs
if ($LASTEXITCODE -ne 0) { Fail "gh pr merge failed with exit code $LASTEXITCODE." }

if ($Sync) {
  Write-Host "→ Syncing local 'main'..."
  git fetch origin | Out-Null
  git switch main   | Out-Null
  git pull --ff-only
}
