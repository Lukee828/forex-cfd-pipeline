param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
Write-Host "PS7 file execution OK at $(Get-Date -Format o)"