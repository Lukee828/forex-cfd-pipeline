param(
  [string]$Dir = "artifacts/allocations"
)
$ErrorActionPreference = "Stop"
$path = Get-ChildItem -Path $Dir -Filter "*_alloc.csv" -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $path) { throw "No *_alloc.csv under $Dir" }
"`n== Allocation: $($path.Name) ==" | Write-Host -ForegroundColor Cyan
$rows = Get-Content $path | Select-Object -Skip 1
$max = 0.0
$data = @()
foreach ($r in $rows) {
  $parts = $r.Split(',')
  $w = [double]$parts[1]
  $data += [pscustomobject]@{ Sleeve=$parts[0]; Weight=$w }
  if ($w -gt $max) { $max = $w }
}
$data | Format-Table -Auto
"`n== Bars ==" | Write-Host -ForegroundColor Cyan
foreach ($d in $data) {
  $n = [int]([math]::Round(($d.Weight / [math]::Max(1e-12,$max)) * 40))
  "{0,-8} | {1} {2:P2}" -f $d.Sleeve, ('#' * $n), $d.Weight
}
