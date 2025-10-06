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
