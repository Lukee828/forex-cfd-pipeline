param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
try {
  Import-Module (Join-Path $here "Dev.psm1") -Force
  Write-Host "Dev tools loaded: Invoke-Precommit, Invoke-Tests, Sync-Registry, Finish-ReleaseTag, New-PullRequest, Protect-DefaultBranch" -ForegroundColor Green
} catch {
  Write-Error "Failed to import Dev.psm1: $($_.Exception.Message)"
  throw
}
