param()
# tools/MT5Api-Account.ps1
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$py   = Join-Path $root ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) { throw "Missing venv python: $py" }
$genDir = Join-Path $root "tools\_gen"
if (-not (Test-Path -LiteralPath $genDir)) { New-Item -ItemType Directory -Path $genDir | Out-Null }
$pyFile = Join-Path $genDir "mt5_account.py"
Set-Content -LiteralPath $pyFile -Encoding UTF8 -Value @(
  'import sys, MetaTrader5 as mt5',
  'if not mt5.initialize():',
  '    print("INIT_FAIL", mt5.last_error()); sys.exit(2)',
  'try:',
  '    print("VERSION", mt5.version())',
  '    print("TERMINAL", mt5.terminal_info())',
  '    print("ACCOUNT", mt5.account_info())',
  'finally:',
  '    mt5.shutdown()',
)
& $py $pyFile

