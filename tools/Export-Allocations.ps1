param(
  [string]$Repo = "C:\Users\speed\Desktop\forex-standalone",
  [string]$MetricsPath = "",
  [string]$PrevWeightsPath = "",
  [string]$CorrPath = ""
)
$ErrorActionPreference="Stop"
Set-Location $Repo
$env:PYTHONPATH = "$PWD\src"

# choose python
$py = Join-Path $PWD ".venv311\Scripts\python.exe"
if (!(Test-Path $py)) {
  $cmd = (Get-Command python -ErrorAction SilentlyContinue)
  if ($cmd) { $py = $cmd.Path } else { $py = "py" }
}

# default demo files (build via objects to avoid quoting issues)
if (-not $MetricsPath) {
  $MetricsPath = Join-Path $PWD "tools\_demo_metrics.json"
  $metrics = @{ TF = @{ sharpe = 1.2; dd = 0.05 }; MR = @{ sharpe = 0.9; dd = 0.04 }; VOL = @{ sharpe = 0.6; dd = 0.03 } }
  $metrics | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $MetricsPath
}
if (-not $PrevWeightsPath) {
  $PrevWeightsPath = Join-Path $PWD "tools\_demo_prev.json"
  $prev = @{ TF = 0.4; MR = 0.4; VOL = 0.2 }
  $prev | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $PrevWeightsPath
}
if (-not $CorrPath) {
  $CorrPath = Join-Path $PWD "tools\_demo_corr.json"
  $pairs = @(@("TF","MR",0.7), @("TF","VOL",0.3), @("MR","VOL",0.2))
  $pairs | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $CorrPath
}

# run python to compute weights and print JSON
$tmp = Join-Path $PWD "tools\_tmp_export_alloc.py"
$pyl = @()
  $pyl += 'import json, sys'
  $pyl += 'from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig'
  $pyl += 'metrics_path, prev_path, corr_path = sys.argv[1:4]'
  $pyl += 'with open(metrics_path, "r", encoding="utf-8") as f: metrics = json.load(f)'
  $pyl += 'with open(prev_path, "r", encoding="utf-8") as f: prev = json.load(f)'
  $pyl += 'with open(corr_path, "r", encoding="utf-8") as f: pairs = json.load(f)'
  $pyl += 'corr = {(a,b): float(c) for a,b,c in pairs}'
  $pyl += 'alloc = MetaAllocator(AllocatorConfig())'
  $pyl += 'w = alloc.allocate(metrics, prev_weights=prev, corr=corr)'
  $pyl += 'print(json.dumps(w))'
Set-Content -Encoding UTF8 -Path $tmp -Value $pyl
$json = & $py $tmp $MetricsPath $PrevWeightsPath $CorrPath
Remove-Item $tmp -ErrorAction SilentlyContinue

# parse result and write CSV
$weights = $null
try { $weights = $json | ConvertFrom-Json } catch { throw "Failed to parse weights JSON: $json" }
$outDir = Join-Path $PWD "artifacts\allocations"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$csv = Join-Path $outDir ($stamp + "_alloc.csv")
$rows = @()
$now = Get-Date -Format "s"
foreach ($k in $weights.PSObject.Properties.Name) {
  $rows += [PSCustomObject]@{ timestamp = $now; sleeve = $k; weight = [double]$weights.$k }
}
$rows | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
Write-Host ("✔ wrote {0}" -f $csv) -ForegroundColor Green
