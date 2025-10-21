Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root   = (git rev-parse --show-toplevel)
$script = Join-Path $root "tools/Audit-State.ps1"
$env:AUDIT_WRITE_REPORT = '0'
& pwsh -NoProfile -File $script
exit $LASTEXITCODE
