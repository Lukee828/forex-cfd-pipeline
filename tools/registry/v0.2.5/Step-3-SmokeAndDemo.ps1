param([string]$Python = ".\.venv311\Scripts\python.exe")
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Fail($m){ Write-Host "[ERR]  $m" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $Python)) { Fail "Python not found at: $Python" }

# Ensure src on sys.path and headless matplotlib
$env:PYTHONPATH = (Resolve-Path .\src).Path
$env:MPLBACKEND = "Agg"

$DB = "data/registry_v025.duckdb"

Info "Init schema"
& $Python -m alpha_factory.registry_cli --db $DB init | Write-Host
if ($LASTEXITCODE -ne 0) { Fail "init failed" }

Info "Register sample rows"
& $Python -m alpha_factory.registry_cli --db $DB register --cfg h1 --metrics "sharpe=1.8" --tags "demo" | Write-Host
if ($LASTEXITCODE -ne 0) { Fail "register h1 failed" }
& $Python -m alpha_factory.registry_cli --db $DB register --cfg h2 --metrics "sharpe=2.2" --tags "demo" | Write-Host
if ($LASTEXITCODE -ne 0) { Fail "register h2 failed" }

Info "Best (top 2)"
& $Python -m alpha_factory.registry_cli --db $DB best --metric sharpe --top 2

Info "Summary"
& $Python -m alpha_factory.registry_cli --db $DB summary --metric sharpe

Info "Backup (retention 7d)"
& $Python -m alpha_factory.registry_cli --db $DB backup --retention 7 | Write-Host
if ($LASTEXITCODE -ne 0) { Fail "backup failed" }

Ok "Smoke succeeded"
