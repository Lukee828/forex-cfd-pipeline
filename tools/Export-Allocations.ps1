Param(
  [ValidateSet("ewma","equal","bayes")] [string]$Mode = "ewma",
  [string]$Metrics = "configs/meta_metrics.json",
  [string]$OutDir  = "artifacts/allocations",
  [switch]$Latest = $true
)
$ErrorActionPreference = "Stop"
$repoRoot = (& git rev-parse --show-toplevel 2>$null); if (-not $repoRoot) { $repoRoot = (Get-Location).Path }
$srcPath  = Join-Path $repoRoot "src"
$py = Join-Path $repoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $py)) { $cmd = Get-Command python -ErrorAction SilentlyContinue; $py = ($cmd ? $cmd.Path : "python"); Write-Warning "Using fallback Python: $py" }
$pkgInit = Join-Path $srcPath "alpha_factory\__init__.py"; if (-not (Test-Path $pkgInit)) { New-Item -ItemType Directory -Force -Path (Split-Path $pkgInit -Parent) | Out-Null; Set-Content -Path $pkgInit -Encoding UTF8 -NoNewline -Value "# package" }
if (-not (Test-Path $Metrics)) { $mDir = Split-Path -Parent $Metrics; if ($mDir -and -not (Test-Path $mDir)) { New-Item -ItemType Directory -Force -Path $mDir | Out-Null }; $m=@("{","  ""TF"":  { ""sharpe"": 1.20, ""dd"": 0.06 },","  ""MR"":  { ""sharpe"": 1.00, ""dd"": 0.05 },","  ""VOL"": { ""sharpe"": 0.80, ""dd"": 0.04 }","}") -join "`n"; Set-Content -Path $Metrics -Encoding UTF8 -NoNewline -Value ($m + "`n") }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$tmpPy = Join-Path $env:TEMP ("alloc_runner_" + [Guid]::NewGuid().ToString("N") + ".py")
$R=@()
$R+="import sys, pathlib"
$R+="src = pathlib.Path(r'"+$srcPath+"').resolve()"
$R+="sys.path.insert(0, str(src))"
$R+="from alpha_factory.cli_meta_alloc import main as cli_main"
$R+="args=[ '--mode', r'"+$Mode+"', '--metrics', r'"+$Metrics+"', '--outdir', r'"+$OutDir+"' ]"
if ($Latest) { $R += "args.append('--write-latest')" }
$R+="cli_main(args)"
$Rtxt = ($R -join "`n") + "`n"
[IO.File]::WriteAllText($tmpPy, $Rtxt, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "PY:  $py" -ForegroundColor DarkCyan
Write-Host "SRC: $srcPath" -ForegroundColor DarkCyan
& $py $tmpPy; if ($LASTEXITCODE -ne 0) { throw "alloc runner exit $LASTEXITCODE" }
Remove-Item $tmpPy -ErrorAction SilentlyContinue
Write-Host "`n== Outputs ==" -ForegroundColor Cyan
Get-ChildItem $OutDir -Filter "*_alloc.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Format-Table -Auto
$latestFile = Join-Path $OutDir "latest.csv"; if (Test-Path $latestFile) { Write-Host "`nlatest.csv:" -ForegroundColor Cyan; Get-Content $latestFile }
Write-Host "`nDone." -ForegroundColor Green
