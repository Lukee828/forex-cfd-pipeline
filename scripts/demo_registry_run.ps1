#requires -Version 7
param(
  [string]$PythonPath = ".\.venv311\Scripts\python.exe",
  [string]$DbPath     = ".\registry.duckdb",
  [string]$CsvPath    = ".\_demo_registry_export.csv",
  [switch]$RegisterSample
)
function Fail($msg) { Write-Error $msg; exit 1 }
if (-not (Test-Path $PythonPath)) { Fail "Python not found at '$PythonPath'." }

$DbAbs  = (Resolve-Path -LiteralPath $DbPath -ErrorAction SilentlyContinue).Path
if (-not $DbAbs) {
  $null = New-Item -Force -ItemType Directory -Path (Split-Path -LiteralPath $DbPath) 2>$null
  $DbAbs = (Resolve-Path -LiteralPath $DbPath -ErrorAction SilentlyContinue).Path
  if (-not $DbAbs) { $DbAbs = [System.IO.Path]::GetFullPath($DbPath) }
}
$CsvAbs = [System.IO.Path]::GetFullPath($CsvPath)

$env:ALPHA_DB       = $DbAbs
$env:ALPHA_CSV      = $CsvAbs
$env:ALPHA_REGISTER = $(if ($RegisterSample) { "1" } else { "0" })

$py = @"
import os, pathlib as p
from src.registry.alpha_registry import AlphaRegistry
import duckdb

db   = p.Path(os.environ["ALPHA_DB"])
csv  = p.Path(os.environ["ALPHA_CSV"])
do_register = os.environ.get("ALPHA_REGISTER","0") == "1"

reg = AlphaRegistry(db).init()
if do_register:
    rid = reg.register("eurusd_h1_v1", {"sharpe": 1.27, "ret": 0.18}, ["fx","h1"])
    print("registered demo id:", rid)

best = reg.get_best("sharpe", 2)
print("\nTop-2 by Sharpe:")
for row in best:
    print(row)

latest_fx = reg.get_latest(tag="fx")
print("\nLatest FX-tagged:")
print(latest_fx)

con = duckdb.connect(str(db))
try:
    df = con.execute("SELECT id, ts, config_hash, metrics, tags FROM alphas ORDER BY id").fetch_df()
finally:
    con.close()
csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(csv, index=False)
print("\nExported CSV ->", csv)
"@

& $PythonPath -c $py
if ($LASTEXITCODE -ne 0) { Fail "Python exited with code $LASTEXITCODE" }

if (Test-Path -LiteralPath $CsvAbs) {
  Write-Host "`nCSV preview (first 5 lines):"
  Get-Content -LiteralPath $CsvAbs | Select-Object -First 5
} else {
  Write-Warning "CSV not found at $CsvAbs"
}
