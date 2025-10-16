#requires -Version 7
[CmdletBinding()]
param(
  [string]$Branch = $null,
  [int]$Tail = 80
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Branch)) {
  try { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() } catch { $Branch = '' }
  if ([string]::IsNullOrWhiteSpace($Branch)) { $Branch = 'main' }
}

Write-Host "`nWatching workflows on branch: $Branch (last $Tail lines)" -ForegroundColor Cyan

# List last few runs for the branch
try {
  $rows = gh run list --branch $Branch -L 4 --json databaseId,workflowName,status,conclusion,url | ConvertFrom-Json
} catch {
  $rows = @()
}

foreach ($r in $rows) {
  Write-Host ("`n--- {0} ({1}) {2}/{3} ---`n{4}" -f $r.workflowName, $r.databaseId, $r.status, ($r.conclusion ?? '-'), $r.url)
  try {
    gh run view $r.databaseId --log | Select-Object -Last $Tail
  } catch {
    Write-Host "[no log yet]" -ForegroundColor DarkGray
  }
}