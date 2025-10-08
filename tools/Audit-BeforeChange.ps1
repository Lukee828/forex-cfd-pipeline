param(
  [string]$Python = ".\.venv\Scripts\python.exe",
  [string[]]$Paths = @("src","tools")
)

$ErrorActionPreference = "Stop"
Write-Host "=== Audit-BeforeChange ===" -ForegroundColor Cyan
Write-Host "PWD: $((Get-Location).Path)" -ForegroundColor DarkGray
Write-Host "Python: $Python" -ForegroundColor DarkGray
if (-not (Test-Path $Python)) {
  Write-Host "WARN: Python not found at $Python" -ForegroundColor Yellow
}

# Gather .py files under given paths
$files = foreach ($p in $Paths) {
  if (Test-Path $p) { Get-ChildItem $p -Recurse -Include *.py | Select-Object -Expand FullName }
}
$files = $files | Sort-Object -Unique
Write-Host "Files to audit: $($files.Count)" -ForegroundColor DarkGray

# 1) Syntax check
$syntaxBad = @()
foreach ($f in $files) {
  & $Python -m py_compile "$f" 2>$null
  if ($LASTEXITCODE -ne 0) { $syntaxBad += $f }
}
if ($syntaxBad.Count) {
  Write-Host "`nSyntax errors in:" -ForegroundColor Red
  $syntaxBad | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  exit 1
}

# 2) Quick import check for key modules (best-effort, non-fatal)
$imports = @(
  "src.risk.time_stop",
  "src.risk.overlay",
  "src.risk.spread_guard",
  "src.risk.be_gate",
  "src.risk.vol_state"
)
foreach ($mod in $imports) {
  & $Python -c "import importlib,sys; importlib.import_module('$mod')" 2>$null
  if ($LASTEXITCODE -ne 0) { Write-Host "WARN: import failed: $mod" -ForegroundColor Yellow }
}

Write-Host "Audit passed ✅" -ForegroundColor Green

# === API CONTRACT AUDIT BEGIN ===
function Invoke-ApiAudit {
  param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
  )
  Write-Host "Running API contract audit..." -ForegroundColor Yellow
  $code = @"
import importlib, inspect, sys

problems = []

# --- time_stop contracts ---
try:
    ts = importlib.import_module("src.risk.time_stop")
    sig_should = str(inspect.signature(ts.should_time_stop))
    sig_is = str(inspect.signature(ts.is_time_stop))
    fields = getattr(ts.TimeStopConfig, "__annotations__", {})
    if sig_should != "(entry_dt: 'datetime', now_dt: 'datetime', bar_minutes: 'int', cfg: 'TimeStopConfig') -> 'tuple[bool, int, int]'":
        problems.append(f"should_time_stop signature drift: {sig_should}")
    if sig_is != "(bars_elapsed: 'int', days_elapsed: 'int', cfg: \"'TimeStopConfig'\")":
        # Accept either quoted or unquoted annotation repr differences
        if "bars_elapsed" not in sig_is or "days_elapsed" not in sig_is or "cfg" not in sig_is:
            problems.append(f"is_time_stop signature drift: {sig_is}")
    for k in ("max_bars","max_days"):
        if k not in fields:
            problems.append(f"TimeStopConfig missing field: {k}")
except Exception as e:
    problems.append(f"import time_stop failed: {e}")

# --- overlay contracts ---
try:
    ov = importlib.import_module("src.risk.overlay")
    sig_init = str(inspect.signature(ov.RiskOverlay.__init__))
    # Must be: (self, cfg, *, spread_fn=None, time_stop_fn=None, breakeven_fn=None)
    wanted = ["cfg", "spread_fn", "time_stop_fn", "breakeven_fn"]
    ok = all(w in sig_init for w in wanted) and "*" in sig_init and "self" in sig_init
    if not ok:
        problems.append(f"RiskOverlay.__init__ signature drift: {sig_init}")
except Exception as e:
    problems.append(f"import overlay failed: {e}")

if problems:
    print("API_AUDIT_FAIL")
    for p in problems:
        print("-", p)
    sys.exit(1)
else:
    print("API_AUDIT_OK")
    sys.exit(0)
"@

  & $PythonExe - <<$code 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "API contract audit FAILED" -ForegroundColor Red
    throw "API audit found problems."
  } else {
    Write-Host "API contract audit OK" -ForegroundColor Green
  }
}
Invoke-ApiAudit -PythonExe '.\.venv\Scripts\python.exe'
# === API CONTRACT AUDIT END ===
