param()
[CmdletBinding()]
param()

[CmdletBinding()]
param(
  [ValidateSet("ticks","rates","rates_range","positions","orders")]
  [string]$Mode = "ticks",
  [string[]]$Symbols = @("XAUUSD","US30","DE40"),
  [string]$Timeframe = "M5",
  [int]$Count = 200,
  [string]$From,
  [string]$To,
  [string]$OutCsv,
  [string]$OutParquet
)
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Missing venv python: $py" }
$args = @("-m","alpha_factory.datafeeds.mt5_feed","--mode",$Mode)
if ($Mode -eq "ticks") { $args += @("--symbols"); $args += $Symbols }
elseif ($Mode -eq "rates") {
  if ($Symbols.Count -ne 1) { throw "rates requires exactly one symbol via -Symbols" }
  $args += @("--symbols",$Symbols[0],"--timeframe",$Timeframe,"--count",$Count)
} elseif ($Mode -eq "rates_range") {
  if ($Symbols.Count -ne 1) { throw "rates_range requires exactly one symbol via -Symbols" }
  if (-not $From -or -not $To) { throw "rates_range requires -From and -To (YYYY-MM-DD or ISO)" }
  $args += @("--symbols",$Symbols[0],"--timeframe",$Timeframe,"--from",$From,"--to",$To)
} elseif ($Mode -eq "positions") { }
elseif ($Mode -eq "orders") { }
if ($OutParquet) { $args += @("--outparquet",$OutParquet) }
elseif ($OutCsv) { $args += @("--outcsv",$OutCsv) }
& $py @args
