param()

# Fail-fast & stricter semantics for PS7 scripts
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
[CmdletBinding()]
param([switch]$HardFail)

$ErrorActionPreference = "Continue"   # never crash the host
$VerbosePreference = "Continue"

function Say([string]$m,[string]$c="White"){ Write-Host $m -ForegroundColor $c }

try {
  $root = (& git rev-parse --show-toplevel 2>$null) ?? (Get-Location).Path
  Say "[INFO] Repo: $root" Cyan

  # Python presence
  $py = @(".venv\Scripts\python.exe","py","python3","python") |
        Where-Object { (Test-Path $_) -or (Get-Command $_ -ErrorAction SilentlyContinue) } |
        Select-Object -First 1
  if ($py) { Say "[OK]  Python => $py" Green } else { Say "[WARN] Python not found" Yellow }

  # Import check (soft)
  if ($py) {
    $code = 'import json,sys;
try:
 import src; print(json.dumps({"ok":True})); sys.exit(0)
except Exception as e:
 print(json.dumps({"ok":False,"err":str(e)})); sys.exit(2)'
    if ($py -eq 'py') { & py -3 -c $code } else { & $py -c $code }
    "import_exit=$LASTEXITCODE"
  }

  # Don’t run formatters or verify here; just say hi.
  Say "[OK]  Minimal audit finished (no side effects)" Green
}
catch {
  Say "[ERR] $($_.Exception.Message)" Red
}
finally {
  Say "`nDone. (This script never closes the terminal.)" Yellow
}
