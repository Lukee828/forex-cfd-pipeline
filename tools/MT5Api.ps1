param()
[CmdletBinding()]
param()

[CmdletBinding()]
param(
  [ValidateSet("ticks","account")]
  [string]$Mode = "ticks",
  [string[]]$Symbols = @("XAUUSD","US30","DE40")
)
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Missing venv python: $py" }
$genDir = Join-Path $root "tools\_gen"
if (-not (Test-Path -LiteralPath $genDir)) { New-Item -ItemType Directory -Path $genDir | Out-Null }
function Write-PyFile { param([string]$Path,[string[]]$Lines) $enc=[Text.UTF8Encoding]::new($false); [IO.File]::WriteAllText($Path, ($Lines -join "`n"), $enc) }
if ($Mode -eq "ticks") {
  $pyFile = Join-Path $genDir "mt5_ticks.py"
  Write-PyFile $pyFile @(
    "import sys, MetaTrader5 as mt5",
    "symbols = sys.argv[1:] or ['XAUUSD','US30','DE40'] ",
    "if not mt5.initialize():",
    "    print('INIT_FAIL', mt5.last_error()); sys.exit(2)",
    "try:",
    "    for s in symbols:",
    "        mt5.symbol_select(s, True)",
    "        t = mt5.symbol_info_tick(s)",
    "        print(f'{s} -> {t}')",
    "finally:",
    "    mt5.shutdown()"
  )
  & $py $pyFile @Symbols
} else {
  $pyFile = Join-Path $genDir "mt5_account.py"
  Write-PyFile $pyFile @(
    "import sys, MetaTrader5 as mt5",
    "if not mt5.initialize():",
    "    print('INIT_FAIL', mt5.last_error()); sys.exit(2)",
    "try:",
    "    print('VERSION', mt5.version())",
    "    print('TERMINAL', mt5.terminal_info())",
    "    print('ACCOUNT', mt5.account_info())",
    "finally:",
    "    mt5.shutdown()"
  )
  & $py $pyFile
}
