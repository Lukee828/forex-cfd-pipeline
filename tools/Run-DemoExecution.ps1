#requires -Version 7
$ErrorActionPreference="Stop"
$Root = (Resolve-Path ".").Path
$Py = ".venv/Scripts/python.exe"; if(-not (Test-Path $Py)){ $Py="python" }
$env:PYTHONPATH = "$Root;$Root\src"
$code = @(
  "from src.execution.demo import DemoBroker",
  "b = DemoBroker()",
  "print(b.send(\"EURUSD\",\"BUY\",1000,1.10001))"
) -join "; "
& $Py -c $code
