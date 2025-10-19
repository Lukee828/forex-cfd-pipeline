param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"
& pwsh -NoProfile -ExecutionPolicy Bypass -File "tools/Verify-Manifest.ps1"
exit $LASTEXITCODE
