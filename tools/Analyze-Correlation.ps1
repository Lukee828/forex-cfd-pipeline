param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
# tools/Analyze-Correlation.ps1
param(
  [Parameter(Mandatory=$true)][string]$InputCsv,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [double]$RedundancyThreshold = 0.97
)
$ErrorActionPreference = "Stop"

# Ensure output dirs
$newOut = New-Item -ItemType Directory -Force -Path $OutDir | Select-Object -ExpandProperty FullName
$telemetryDir = Join-Path "reports" "telemetry"
$newTel = New-Item -ItemType Directory -Force -Path $telemetryDir | Select-Object -ExpandProperty FullName
$telemetryPath = Join-Path $newTel "events.jsonl"

# Inline python to compute corr / redundancy and export CSV+HTML
$py = @"
import json, sys, pathlib
import pandas as pd
from src.analytics.corr_matrix import corr_matrix, drop_redundant

inp, outdir, thr = sys.argv[1], sys.argv[2], float(sys.argv[3])
df = pd.read_csv(inp)
reduced, report = drop_redundant(df, threshold=thr)
cm = corr_matrix(df)

outdir = pathlib.Path(outdir)
outdir.mkdir(parents=True, exist_ok=True)
cm.to_csv(outdir / "corr_matrix.csv")

# Simple HTML heatmap using Pandas styling to avoid extra deps
html = cm.style.background_gradient(axis=None).set_caption("Correlation Matrix").to_html()
(outdir / "corr_matrix.html").write_text(html, encoding="utf-8")

# Emit telemetry line to stdout for PS to persist
event = {
  "event": "correlation_analyzed",
  "redundancy_threshold": thr,
  "n_features_in": int(df.select_dtypes(include="number").shape[1]),
  "n_features_kept": int(len(report.kept_columns)),
  "n_pairs_dropped": int(len(report.dropped_pairs))
}
print(json.dumps(event))
"@

$evt = & python - "$InputCsv" "$newOut" "$RedundancyThreshold" @py
# Append telemetry
Add-Content -Encoding UTF8 -Path $telemetryPath -Value $evt

Write-Host "✅ Correlation analysis complete:"
Write-Host "  • CSV  : $newOut\corr_matrix.csv"
Write-Host "  • HTML : $newOut\corr_matrix.html"
Write-Host "  • Telemetry appended -> $telemetryPath"
