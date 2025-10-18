param()
# Simple telemetry helper; writes a line to .meta/telemetry.log and Step Summary in CI.
param(
  [Parameter(Mandatory)][string]$Message
)
$log = ".meta/telemetry.log"
$ts = (Get-Date).ToString("s")
Add-Content -LiteralPath $log -Value "$ts`t$Message"
if ($env:GITHUB_STEP_SUMMARY) {
  Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value "`n- $Message"
}

