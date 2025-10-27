param(
  [string]$OutPath = "artifacts/reports/latest.md",
  [switch]$NoTail
)
$ErrorActionPreference = "Stop"

# Resolve script folder even when run interactively
$ScriptDir = if ($PSScriptRoot -and $PSScriptRoot -ne "") {
  $PSScriptRoot
} else {
  $p = $MyInvocation.MyCommand.Path
  if ($p) { Split-Path -Parent $p } else { (Resolve-Path ".").Path }
}
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

Write-Host "=== Daily Report Builder ===" -ForegroundColor Cyan
Write-Host ("Repo: {0}" -f $RepoRoot)
Write-Host ("Out : {0}" -f $OutPath)

# Ensure output folder
$outDir = Split-Path -Parent $OutPath
if ($outDir -and $outDir -ne "") { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }

# 1) Run Meta Allocator
Write-Host "`n→ Running Meta Allocator..." -ForegroundColor Yellow
$runAlloc = Join-Path $ScriptDir "Run-MetaAllocator.ps1"
if (!(Test-Path $runAlloc)) { throw "Missing: $runAlloc" }
pwsh -File $runAlloc

# 2) Build Risk Report (with allocator section)
Write-Host "`n→ Building risk report..." -ForegroundColor Yellow
$riskReport = Join-Path $ScriptDir "Risk-Report.ps1"
if (!(Test-Path $riskReport)) { throw "Missing: $riskReport" }
pwsh -File $riskReport -OutPath $OutPath -IncludeAlloc

# 3) Optional tail preview
if (-not $NoTail.IsPresent) {
  Write-Host "`n--- Report Tail ---" -ForegroundColor DarkCyan
  if (Test-Path $OutPath) { Get-Content $OutPath -Tail 40 } else { Write-Warning "Report not found: $OutPath" }
}

Write-Host "`n✔ Daily report complete → $OutPath" -ForegroundColor Green
