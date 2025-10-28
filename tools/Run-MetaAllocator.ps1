Param(
  [ValidateSet("ewma","equal","bayes")] [string]$Mode = "ewma",
  [string]$OutDir = "artifacts/allocations"
)
$ErrorActionPreference = 'Stop'

$repoRoot = (& git rev-parse --show-toplevel 2>$null) ; if (-not $repoRoot) { $repoRoot = (Get-Location).Path }
$srcPath  = Join-Path $repoRoot 'src'
$env:PYTHONPATH = $srcPath
$env:AF_SRC     = $srcPath
$venvPy = Join-Path $repoRoot '.venv311\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { Write-Warning "'.venv311\\Scripts\\python.exe' not found, using 'python'"; $venvPy = 'python' }

$py = @"
import os, sys, time, pathlib, json
af_src = os.environ.get("AF_SRC")
if af_src and af_src not in sys.path: sys.path.insert(0, af_src)
from alpha_factory.meta_allocator import MetaAllocator, AllocatorConfig
mode = sys.argv[1] if len(sys.argv)>1 else "ewma"
metrics = {"TF":{"sharpe":1.2,"dd":0.06},"MR":{"sharpe":1.0,"dd":0.05},"VOL":{"sharpe":0.8,"dd":0.04}}
w = MetaAllocator(AllocatorConfig(mode=mode)).allocate(metrics)
print("MODE:", mode); print("ALLOC:", w)
ts = time.strftime("%Y%m%d_%H%M%S")
outdir = pathlib.Path(sys.argv[2] if len(sys.argv)>2 else "artifacts/allocations"); outdir.mkdir(parents=True, exist_ok=True)
csv = outdir / f"{ts}_alloc.csv"
csv.write_text("Sleeve,Weight\\n" + "\\n".join(f"{k},{v}" for k,v in w.items()), encoding="utf-8")
print("CSV:", csv)
"@
$tmp = Join-Path $env:TEMP ("meta_alloc_" + [Guid]::NewGuid().ToString('N') + ".py")
Set-Content -Path $tmp -Encoding utf8 -NoNewline -Value ($py -replace "`r`n","`n")
try {
  & $venvPy $tmp $Mode $OutDir
  if ($LASTEXITCODE -ne 0) { throw "Python exited with code $LASTEXITCODE" }
} finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
