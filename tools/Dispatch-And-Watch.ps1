param(
  [string]$Branch = (git rev-parse --abbrev-ref HEAD).Trim(),
  [int]$Tail = 120
)

function Get-LatestRunId {
  param([string]$Branch,[string]$WorkflowNameLike)
  $rows = gh run list --branch $Branch -L 40 --json databaseId,workflowName,createdAt | ConvertFrom-Json
  $rows |
    Where-Object { $_.workflowName -and ($_.workflowName -match [regex]::Escape($WorkflowNameLike)) } |
    Sort-Object createdAt -Descending |
    Select-Object -ExpandProperty databaseId -First 1
}

function Wait-And-Show {
  param([int64]$RunId,[int]$Tail = 120)
  gh run watch $RunId --exit-status
  $s = gh run view $RunId --json workflowName,status,conclusion,createdAt,updatedAt,url | ConvertFrom-Json
  "{0} → status={1} conclusion={2}  created={3}  updated={4}`n{5}" -f $s.workflowName,$s.status,$s.conclusion,$s.createdAt,$s.updatedAt,$s.url | Write-Host
  "`n--- Last $Tail lines ---" | Write-Host
  gh run view $RunId --log | Select-Object -Last $Tail
}

Write-Host "Branch: $Branch"

# Kick both
gh workflow run "Tests (pytest)"      --ref $Branch | Out-Null
gh workflow run "Lint (Ruff + Black)" --ref $Branch | Out-Null

Start-Sleep -Seconds 3

$testId = Get-LatestRunId -Branch $Branch -WorkflowNameLike 'Tests (pytest)'
$lintId = Get-LatestRunId -Branch $Branch -WorkflowNameLike 'Lint (Ruff + Black)'

if ($testId) { Write-Host "`nWaiting for Tests (pytest) run $testId ..."; Wait-And-Show -RunId $testId -Tail $Tail }
if ($lintId) { Write-Host "`nWaiting for Lint (Ruff + Black) run $lintId ..."; Wait-And-Show -RunId $lintId -Tail $Tail }
