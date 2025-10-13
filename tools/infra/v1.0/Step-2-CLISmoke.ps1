param(
  [string]$PythonExe,                     # optional; will auto-pick if omitted
  [string]$Db,
  [string]$Csv,
  [string]$Html
)

$ErrorActionPreference = "Stop"

# Project root and make src importable
$root = (Resolve-Path .).Path
$env:PYTHONPATH = Join-Path $root 'src'

# Prefer project venv, else system python
if (-not $PSBoundParameters.ContainsKey('PythonExe')) {
  $venv = Join-Path $root '.venv311'
  $py = if ($IsWindows) { Join-Path $venv 'Scripts/python.exe' } else { Join-Path $venv 'bin/python' }
  if (Test-Path $py) { $PythonExe = $py } else { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
}

# Portable outputs
if (-not $Db)   { $Db   = Join-Path $root 'cli_smoke.duckdb' }
if (-not $Csv)  { $Csv  = Join-Path $root 'cli_best.csv' }
if (-not $Html) { $Html = Join-Path $root 'cli_summary_dark.html' }

# Diag
Write-Host ("Python: {0}" -f $PythonExe)
Write-Host ("DB:     {0}" -f $Db)
Write-Host ("CSV:    {0}" -f $Csv)
Write-Host ("HTML:   {0}" -f $Html)

# Clean
Remove-Item $Db,$Csv,$Html -ErrorAction SilentlyContinue

# Seed + exports
& $PythonExe -m alpha_factory.registry_cli --db $Db init
& $PythonExe -m alpha_factory.registry_cli --db $Db register --cfg h1 --metrics "sharpe=1.8" --tags demo
& $PythonExe -m alpha_factory.registry_cli --db $Db register --cfg h2 --metrics "sharpe=2.4" --tags demo
& $PythonExe -m alpha_factory.registry_cli --db $Db export --what best    --metric sharpe --top 1 --format csv  --out $Csv
& $PythonExe -m alpha_factory.registry_cli --db $Db export --what summary --metric sharpe          --format html --theme dark --out $Html

# Assertions
if (-not (Test-Path -LiteralPath $Csv))  { throw "best CSV not created: $Csv" }
if (-not (Test-Path -LiteralPath $Html)) { throw "summary HTML not created: $Html" }

"== CSV head ==";  Get-Content -LiteralPath $Csv  | Select-Object -First 2
"== HTML head =="; Get-Content -LiteralPath $Html | Select-Object -First 3
Write-Host "[OK] CLI smoke passed" -ForegroundColor Green

# --- Python self-heal guard (handles broken venvs that lack pyvenv.cfg) ---
try {
  & $PythonExe -c "import sys; print('OK', sys.executable)" | Out-Null
} catch {
  Write-Warning "Python ''$PythonExe'' looks broken. Trying fallbacks..."
  $candidates = @(
    (Join-Path $root ''.venv311\Scripts\python.exe''),
    (Get-Command py      -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }),
    (Get-Command python  -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
  ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
  foreach ($cand in $candidates) {
    try {
      & $cand -c "print('OK')" | Out-Null
      $PythonExe = $cand
      Write-Host "Using Python: $PythonExe"
      break
    } catch { }
  }
}
# --------------------------------------------------------------------------
