param(
  [string]$Branch = (git rev-parse --abbrev-ref HEAD).Trim(),
  [int]$Tail = 200,
  [switch]$TestsOnly,
  [switch]$LintOnly
)

function Get-LatestRunId {
  param([string]$Branch,[string]$Workflow)
  $rows = gh run list --branch $Branch -L 40 --json databaseId,workflowName,createdAt | ConvertFrom-Json
  $rows |
    Where-Object { $_.workflowName -and ($_.workflowName -eq $Workflow) } |
    Sort-Object createdAt -Descending |
    Select-Object -ExpandProperty databaseId -First 1
}

function Wait-And-Show {
  param([int64]$RunId,[int]$Tail)
  gh run watch $RunId --exit-status | Out-Null
  $s = gh run view $RunId --json workflowName,status,conclusion,createdAt,updatedAt,url | ConvertFrom-Json
  "{0} → status={1} conclusion={2}  created={3}  updated={4}`n{5}" -f $s.workflowName,$s.status,$s.conclusion,$s.createdAt,$s.updatedAt,$s.url | Write-Host
  "`n--- Last $Tail lines ---" | Write-Host
  gh run view $RunId --log | Select-Object -Last $Tail
}

Write-Host "Branch: $Branch"

if(-not $LintOnly){
  gh workflow run "Tests (pytest)" --ref $Branch | Out-Null
}
if(-not $TestsOnly){
  gh workflow run "Lint (Ruff + Black)" --ref $Branch | Out-Null
}

Start-Sleep -Seconds 3

if(-not $LintOnly){
  $testId = Get-LatestRunId -Branch $Branch -Workflow 'Tests (pytest)'
  if ($testId) { Write-Host "`nWaiting for Tests (pytest) run $testId ..."; Wait-And-Show -RunId $testId -Tail $Tail }
}
if(-not $TestsOnly){
  $lintId = Get-LatestRunId -Branch $Branch -Workflow 'Lint (Ruff + Black)'
  if ($lintId) { Write-Host "`nWaiting for Lint (Ruff + Black) run $lintId ..."; Wait-And-Show -RunId $lintId -Tail $Tail }
}
