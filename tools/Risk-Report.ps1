param(
  [Parameter(Mandatory)] [string]$OutPath,
  [string]$Title = "Daily Risk Report",
  [switch]$IncludeAlloc
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path (Split-Path $OutPath) | Out-Null

# repo meta
$sha = ""
try { $sha = (git rev-parse --short=7 HEAD).Trim() } catch { $sha = "" }
$ts  = Get-Date -Format s

# build report body
$lines = @()
$lines += "# $Title"
$lines += ""
$lines += ("Generated: {0}" -f $ts)
$lines += ($sha -ne "" ? ("Commit: {0}" -f $sha) : "")
$lines += ""
$lines += "## Summary"
$lines += "- Risk scan: (attach your scan summary here)"
$lines += "- Governor status: (ok/warn/breach)"
$lines += ""
$lines += "## Notes"
$lines += "- Add any manual notes here."

Set-Content -Encoding UTF8 -Path $OutPath -Value ($lines -join "`n")
Write-Host ("✔ wrote {0}" -f $OutPath) -ForegroundColor Green

if ($IncludeAlloc.IsPresent) {
  $post = Join-Path $PSScriptRoot "Post-Report-Include-Alloc.ps1"
  if (Test-Path $post) {
    pwsh -File $post -ReportPath $OutPath
  }
}
