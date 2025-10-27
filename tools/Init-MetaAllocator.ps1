$ErrorActionPreference="Stop"
Set-Location "C:\Users\speed\Desktop\forex-standalone"
$env:PYTHONPATH = "$PWD\src"
.\.venv311\Scripts\python.exe -m pytest -q tests/alpha_factory/test_meta_allocator_smoke.py -vv --maxfail=1
