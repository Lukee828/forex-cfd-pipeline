param()
[CmdletBinding()]
param()

[CmdletBinding()]
param(
  [string]$Symbols = "XAUUSD,US30,DE40",   # single string; we will split on commas/whitespace
  [string]$Timeframe = "M5",
  [int]$Count = 300,
  [string]$FromDt,
  [string]$ToDt,
  [string]$OutParquetDir = "data\features",
  [string]$OutDuckDB = "data\feature_store.duckdb"
)
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Missing venv python: $py" }

# Normalize symbols: split on commas/whitespace, drop empties
$SymbolsList = ($Symbols -split '[,\s]+' | Where-Object { $_ -ne '' })

# Build args deterministically; only add range if BOTH dates provided
$argv = @(
  "-m","alpha_factory.research.research_loop",
  "--timeframe",$Timeframe,
  "--out_parquet_dir",$OutParquetDir,
  "--out_duckdb",$OutDuckDB
)
if ($FromDt -and $ToDt) {
  $argv += @("--from_dt",$FromDt,"--to_dt",$ToDt)
} else {
  $argv += @("--count",$Count)
}
$argv += @("--symbols"); $argv += $SymbolsList

Write-Host "PYTHON ARGS:" ($argv -join ' ')
& $py @argv
