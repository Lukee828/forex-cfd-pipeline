param(
  [string]$Pairs  = "EURUSD,GBPUSD",
  [ValidateSet("1m","5m","1h","1d")]
  [string]$TF     = "1h",
  [Parameter(Mandatory=$true)][string]$Start,
  [Parameter(Mandatory=$true)][string]$End,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'

# --- Validate dates (ISO) ----------------------------------------------------
$iso = '^\d{4}-\d{2}-\d{2}$'
if ($Start -notmatch $iso -or $End -notmatch $iso) {
  throw "Dates must be ISO format YYYY-MM-DD. Example: -Start 2025-05-10 -End 2025-05-15"
}

# --- Normalize pairs -> array ------------------------------------------------
$pairs = @()
if ($Pairs) {
  $pairs = $Pairs -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
}
if (-not $pairs -or $pairs.Count -eq 0) {
  throw "No symbols provided. Pass -Pairs 'EURUSD,GBPUSD'."
}

# --- Default OutDir if not provided -----------------------------------------
if (-not $OutDir -or -not $OutDir.Trim()) {
  $safeTf = $TF.ToLower()
  $OutDir = Join-Path "artifacts" "prices_${safeTf}"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Output directory: $OutDir" -ForegroundColor Cyan
Write-Host "Symbols: $($pairs -join ', ')" -ForegroundColor Cyan

# --- Ensure Python is available ---------------------------------------------
try {
  $pyver = (& python --version) 2>$null
  if (-not $pyver) { throw "python not found on PATH" }
  Write-Host "Using $pyver" -ForegroundColor DarkGray
} catch {
  throw "Python is required (python on PATH). Install Python 3.11+ and retry. $_"
}

# --- Ensure dukascopy lib exists (prefer dukascopy-python) -------------------
function Test-PythonImport($moduleName) {
  & python -c "import importlib; import sys; 
try:
    importlib.import_module('$moduleName'); 
    sys.exit(0)
except Exception:
    sys.exit(1)
" | Out-Null
  return ($LASTEXITCODE -eq 0)
}

$hasDukaPy = Test-PythonImport 'dukascopy_python'
$hasDuka   = if (-not $hasDukaPy) { Test-PythonImport 'dukascopy' } else { $false }

if (-not $hasDukaPy -and -not $hasDuka) {
  Write-Host "Installing pip package 'dukascopy-python' (one-time)..." -ForegroundColor Yellow
  & python -m pip install --upgrade pip | Out-Null
  & python -m pip install dukascopy-python
  # Re-check
  $hasDukaPy = Test-PythonImport 'dukascopy_python'
  $hasDuka   = if (-not $hasDukaPy) { Test-PythonImport 'dukascopy' } else { $false }
  if (-not $hasDukaPy -and -not $hasDuka) {
    throw "Failed to import dukascopy-python/dukascopy after install."
  }
}

# --- Run downloader per symbol ----------------------------------------------
$results = @()
$errors  = @()

foreach ($sym in $pairs) {
  $outFile = Join-Path $OutDir "$sym.parquet"
  Write-Host "→ $sym  ($TF)  $Start..$End" -ForegroundColor Green
  try {
    & python -m src.data.dukascopy_downloader `
        --symbol $sym `
        --tf $TF `
        --start $Start `
        --end $End `
        --out $outFile

    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outFile)) {
      $sz = (Get-Item -LiteralPath $outFile).Length
      $results += [pscustomobject]@{
        Symbol=$sym; TF=$TF; Start=$Start; End=$End; Path=$outFile; Bytes=$sz
      }
    } else {
      $errors += ("{0}: downloader exited with code {1} or no file written" -f $sym,$LASTEXITCODE)
    }
  } catch {
    $errors += ("{0}: {1}" -f $sym,$_.Exception.Message)
  }
}

# --- Report ------------------------------------------------------------------
if ($results.Count -gt 0) {
  Write-Host "`nSaved:" -ForegroundColor Cyan
  $results | Format-Table -AutoSize
} else {
  Write-Host "`nNo files were saved." -ForegroundColor Yellow
}

if ($errors.Count -gt 0) {
  Write-Host "`nErrors:" -ForegroundColor Red
  $errors | ForEach-Object { " - $_" } | Write-Output
}