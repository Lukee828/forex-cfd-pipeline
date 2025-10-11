#requires -Version 7.0
$ErrorActionPreference = "Stop"
Write-Host "[ensure-agg] Verifying matplotlib..." -ForegroundColor Cyan

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Error "python not found on PATH"; exit 2 }

# use a compact -c payload to avoid quoting pitfalls
$code = @(
  'import sys'
  'print("Python:", sys.version.split()[0])'
  'try:'
  '    import matplotlib'
  '    print("matplotlib:", matplotlib.__version__)'
  '    print("backend (rc):", matplotlib.get_backend())'
  '    from matplotlib.backends.backend_agg import FigureCanvasAgg'
  '    print("Agg backend import: OK")'
  'except Exception as e:'
  '    print("FATAL:", e)'
  '    raise'
) -join '; '

$lines = & $py.Path -c $code 2>&1
$rc = $LASTEXITCODE
$lines | ForEach-Object { Write-Host $_ }

if ($rc -ne 0) { Write-Error "matplotlib/Agg verification failed"; exit $rc }
Write-Host "`n[ensure-agg] OK - Matplotlib present and Agg backend available." -ForegroundColor Green
