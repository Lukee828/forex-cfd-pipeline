param(
  [string]$Root = "tools",
  [switch]$IncludeModules,   # include .psm1 too
  [switch]$Apply            # actually write changes (preview if not set)
)

$ErrorActionPreference = 'Stop'

$patterns = @{
  HasParam  = '^\s*param\s*\('
  LeadBlock = '^\s*<#[\s\S]*?#>\s*'  # leading comment/PSScriptInfo block
}

$header = @"
param()

# Fail-fast & stricter semantics for PS7 scripts
`$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

"@

$exts = @("*.ps1")
if ($IncludeModules) { $exts += "*.psm1" }

$files = foreach ($ext in $exts) { Get-ChildItem $Root -Recurse -File -Include $ext }
if (-not $files) { Write-Host "No PowerShell files found under $Root" -ForegroundColor Yellow; exit 0 }

$toFix = @()
foreach ($f in $files) {
  $raw = Get-Content -Raw $f.FullName
  if ($raw -notmatch $patterns.HasParam) { $toFix += $f }
}

if (-not $toFix) { Write-Host "All matched files already have a param() block." -ForegroundColor Green; exit 0 }

Write-Host ("Found {0} file(s) missing param():`n - {1}" -f $toFix.Count, ($toFix.FullName -join "`n - ")) -ForegroundColor Cyan

foreach ($f in $toFix) {
  $raw = Get-Content -Raw $f.FullName
  $m = [regex]::Match($raw, $patterns.LeadBlock, [System.Text.RegularExpressions.RegexOptions]::Singleline)
  $ins = if ($m.Success) { $m.Length } else { 0 }
  $new = $raw.Insert($ins, $header)

  if ($Apply) {
    Set-Content -Encoding UTF8 -NoNewline -Path $f.FullName -Value $new
    Write-Host "Fixed: $($f.FullName)" -ForegroundColor Green
  } else {
    Write-Host "Would fix: $($f.FullName)" -ForegroundColor Yellow
  }
}

if (-not $Apply) { Write-Host "`n(Preview only) Re-run with -Apply to write changes." -ForegroundColor Yellow }
