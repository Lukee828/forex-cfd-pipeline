#requires -Version 7
$ErrorActionPreference="Stop"
$Root = (Resolve-Path ".").Path
$Py = ".venv/Scripts/python.exe"; if(-not (Test-Path $Py)){ $Py="python" }
$env:PYTHONPATH = "$Root;$Root\src"
& $Py -m src.backtest.cli @args
