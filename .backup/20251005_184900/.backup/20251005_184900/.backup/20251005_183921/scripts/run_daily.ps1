param([string]$Prefix = ("DAILY_{0:yyyyMMdd}" -f (Get-Date)))

$ErrorActionPreference = "Stop"

# --- settings ---
$ProjectRoot = "C:\Users\speed\Desktop\Forex CFD's system"
$PythonExe   = "C:\Users\speed\AppData\Local\Programs\Python\Python313\python.exe"
$ConfigYaml  = Join-Path $ProjectRoot "config\production.yaml"
$LogFile     = Join-Path $ProjectRoot ("logs\daily_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))

# --- env for MT5 (fallbacks only if Task doesn't set them) ---
if (-not $env:MT5_LOGIN)    { $env:MT5_LOGIN    = "52508263" }
if (-not $env:MT5_PASSWORD) { $env:MT5_PASSWORD = "@!DOhN5sR0z9Kk" }
if (-not $env:MT5_SERVER)   { $env:MT5_SERVER   = "ICMarketsEU-Demo" }

# --- run ---
Set-Location $ProjectRoot
& $PythonExe -m src.exec.daily_run `
  --config $ConfigYaml `
  --out_prefix $Prefix `
  --mt5_verify_positions *>> $LogFile

Get-ChildItem "$ProjectRoot\logs\*.log" | Sort LastWriteTime -Descending | Select -Skip 14 | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem "$ProjectRoot\executions\reconcile_*.csv" | Sort LastWriteTime -Descending | Select -Skip 30 | Remove-Item -Force -ErrorAction SilentlyContinue
