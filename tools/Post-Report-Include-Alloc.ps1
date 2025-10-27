param(
  [Parameter(Mandatory=$true)][string]$ReportPath,
  [string]$Repo = "$PSScriptRoot\.."
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path $Repo)

# 1) Build/refresh allocator section
pwsh -File tools/Risk-Alloc-Section.ps1 -Repo $PWD | Out-Null
$section = "docs/sections/allocations.md"
if (!(Test-Path $section)) { throw "Missing section: $section" }

# 2) Verify target report exists
if (!(Test-Path $ReportPath)) {
  throw "Report not found: $ReportPath (generate your base Risk-Report first)"
}

# 3) Append section with a neat delimiter
$delim = @()
$delim += ""
$delim += "---"
$delim += ""
Add-Content -Encoding UTF8 -Path $ReportPath -Value ($delim -join "`n")

$secLines = Get-Content $section -Encoding UTF8
Add-Content -Encoding UTF8 -Path $ReportPath -Value ($secLines -join "`n")

Write-Host ("✔ appended allocator section to {0}" -f (Resolve-Path $ReportPath)) -ForegroundColor Green
