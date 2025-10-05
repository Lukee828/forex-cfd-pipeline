param([string]$RunPath = "")
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (!(Test-Path $py)) { throw "Missing .venv Python at .\.venv\Scripts\python.exe" }
$argv = @("tools\Summarize-Run.py")
if ($RunPath) { $argv += @("--runpath", $RunPath) }
& $py @argv
