# tools/MT5Api-Ticks.ps1
[CmdletBinding()]
param([string[]]$Symbols = @("XAUUSD","US30.cash","GER40.cash"))
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Missing venv python: $py" }
$genDir = Join-Path $root "tools\_gen"
if (-not (Test-Path -LiteralPath $genDir)) { New-Item -ItemType Directory -Path $genDir | Out-Null }
$pyFile = Join-Path $genDir "mt5_ticks.py"
Set-Content -LiteralPath $pyFile -Encoding UTF8 -Value @(
  'import sys, MetaTrader5 as mt5',
  'symbols = sys.argv[1:] or ["XAUUSD","US30.cash","GER40.cash"]',
  'if not mt5.initialize():',
  '    print("INIT_FAIL", mt5.last_error()); sys.exit(2)',
  'try:',
  '    for s in symbols:',
  '        t = mt5.symbol_info_tick(s)',
  '        print(f"{s} -> {t}")',
  'finally:',
  '    mt5.shutdown()',
)
& $py $pyFile @Symbols
