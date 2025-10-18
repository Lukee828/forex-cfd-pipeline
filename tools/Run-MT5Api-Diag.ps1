param()
$root = "C:\Users\speed\Desktop\forex-standalone"
$py   = "$root\.venv311\Scripts\python.exe"
$diag = "$root\tests\mt5_api_diag.py"
Set-Location $root
& $py $diag

