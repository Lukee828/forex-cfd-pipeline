#requires -Version 7
param(
  [string]$Csv = "",
  [switch]$Demo
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Py = Join-Path $Root ".venv/Scripts/python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = "$Root;$Root\src"
try {
  if ($Demo -or -not (Test-Path $Csv)) {
    $tmp = Join-Path $env:TEMP ("ma_demo_" + [guid]::NewGuid().ToString("N") + ".py")
    Set-Content -LiteralPath $tmp -Encoding UTF8 -Value @(
      "from __future__ import annotations"
      "import pandas as pd"
      "from src.infra.meta_allocator import MetaAllocator, MetaAllocatorConfig"
      "rows = pd.DataFrame({'sharpe':[1.2,0.8,0.3], 'dd':[0.10,0.05,0.20]}, index=['ZZ','S2E','MR'])"
      "rs = {'ZZ':1.0, 'S2E':0.9, 'MR':0.4}"
      "w = MetaAllocator(MetaAllocatorConfig()).compute_weights(rows, risk_scale=rs)"
      "print(w.to_string())"
    )
    & $Py $tmp
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  } else {
    $tmp = Join-Path $env:TEMP ("ma_run_" + [guid]::NewGuid().ToString("N") + ".py")
    Set-Content -LiteralPath $tmp -Encoding UTF8 -Value @(
      "from __future__ import annotations"
      "import pandas as pd"
      "from src.infra.meta_allocator import MetaAllocator, MetaAllocatorConfig"
      "df = pd.read_csv(r'$Csv')"
      "df = df.set_index('index') if 'index' in df.columns else df.set_index(df.columns[0])"
      "w = MetaAllocator(MetaAllocatorConfig()).compute_weights(df)"
      "print(w.to_string())"
    )
    & $Py $tmp
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  }
} finally { $env:PYTHONPATH = $old }
