param()
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
& pwsh -NoProfile -ExecutionPolicy Bypass -File "tools/Verify-Manifest.ps1"
exit $LASTEXITCODE
