param(
  [string]$Repo = "$PSScriptRoot\..",
  [string]$AllocDir = "artifacts/allocations",
  [string]$OutPath = "docs/sections/allocations.md"
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path $Repo)
$allocAbs = Join-Path $PWD $AllocDir
if (!(Test-Path $allocAbs)) { throw "Alloc dir not found: $allocAbs" }
$latest = Get-ChildItem -Path $allocAbs -Filter *.csv -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw "No allocation CSVs in $allocAbs" }
$rows = Import-Csv -Path $latest.FullName
$rows = $rows | Sort-Object sleeve
$sum  = ($rows | ForEach-Object { [double]$_.weight }) | Measure-Object -Sum | Select-Object -ExpandProperty Sum
$dir = Split-Path $OutPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$md = @()
$md += "# Current Meta Allocator Weights"
$md += ""
$md += ("_Source:_ ``{0}``  ·  _Generated:_ {1}Z" -f $latest.Name, (Get-Date).ToUniversalTime().ToString("s"))
$md += ""
$md += "| Sleeve | Weight |"
$md += "|-------:|------:|"
foreach ($r in $rows) {
  $w = [double]$r.weight
  $md += ("| {0} | {1:N4} |" -f $r.sleeve, $w)
}
$md += ""
$md += ("**Sum:** {0:N6}" -f $sum)
Set-Content -Encoding UTF8 -Path $OutPath -Value ($md -join "`n")
Write-Host ("✔ wrote {0}" -f (Resolve-Path $OutPath)) -ForegroundColor Green
