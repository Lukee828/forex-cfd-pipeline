param(
  [Parameter(Mandatory)][string]$InputCsv,
  [string]$OutDir = "reports/redundancy",
  [double]$Threshold = 0.9
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not (Test-Path $InputCsv)) { throw "Input CSV not found: $InputCsv" }
$null = New-Item -ItemType Directory -Force -Path $OutDir

# Python one-liner to run filter
$py = @"
import sys, pandas as pd
from src.analytics.redundancy import redundancy_filter
df = pd.read_csv(sys.argv[1])
kept, dropped = redundancy_filter(df, threshold=float(sys.argv[2]))
pd.Series(kept, name="kept").to_csv(sys.argv[3], index=False)
pd.Series(dropped, name="dropped").to_csv(sys.argv[4], index=False)
print(f"kept={len(kept)}, dropped={len(dropped)}")
"@
$tmp = Join-Path $env:TEMP ("redundancy_run_"+[guid]::NewGuid().ToString("N")+".py")
[IO.File]::WriteAllText($tmp, $py, [Text.UTF8Encoding]::new($false))

$keptCsv    = Join-Path $OutDir "kept.csv"
$droppedCsv = Join-Path $OutDir "dropped.csv"

python $tmp $InputCsv $Threshold $keptCsv $droppedCsv | Tee-Object -Variable _summary | Out-Null
Remove-Item $tmp -Force

# telemetry
& "$PSScriptRoot/Telemetry.ps1" -Message "Redundancy run: $(_summary) -> $OutDir"
Write-Host "✅ Redundancy report written to: $OutDir" -ForegroundColor Green
